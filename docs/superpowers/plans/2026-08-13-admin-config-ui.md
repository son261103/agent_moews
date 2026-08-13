# Admin Config UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a frontend admin page (`/admin`) to import an OpenAPI spec + set base URL/token (applied via `POST /admin/reload` without restarting the backend) and to create/edit/delete skills stored in the DB.

**Architecture:** New `AdminStore` (aiosqlite, same pattern as `ChatStore`) with `skills` and `openapi_config` tables in `agent_moew.db`. `SkillRegistry` is rewritten to be DB-backed (async) so the agent sees skill changes immediately; its public API (`SkillInfo`, `list_skills`, `load`, `build_skills_discovery`, `get_skill_registry`) is preserved so `tools.py`/`builder.py` only need small async adjustments. New admin routes under `/api/v1/admin`; `POST /admin/reload` materializes the DB spec to `data/imported_openapi.json`, sets settings, rebuilds the graph, and swaps it in.

**Tech Stack:** Python 3.12 / FastAPI / aiosqlite / LangGraph (backend), Next.js 16 App Router / React 19 / Tailwind v4 (frontend).

## Global Constraints

- Tests run from `backend/` via `.venv/bin/python -m pytest` (asyncio_mode="auto" — async tests need no runner).
- Tools return strings, never raise. API handlers return HTTPException with `{"detail": "..."}`.
- Skill `load()` raises `KeyError(f"Skill not found: {name}")`; `load_skill` tool catches it and returns `f"Skill not found: {name}"`.
- `SkillInfo` keeps `name`, `description`, `path` fields — set `path` to `None` (DB-backed).
- AdminStore follows the ChatStore pattern exactly: aiosqlite, `connect()/close()`, `assert self._conn is not None` guards, `await cursor.close()` after fetchall.
- Route tests use `fastapi.testclient.TestClient` + `create_app(test_settings)` with dummy keys (`openai_api_key="sk-test"`, `tavily_api_key="tvly-test"`, `langsmith_api_key="ls-test"`, `db_path=str(tmp_path / "test.db")`) — same as `tests/test_threads.py:47-52`.
- `backend/specs/` and `data/` are gitignored — never commit generated spec files.
- LSP import-resolution errors are pre-existing noise (LSP ignores `.venv`) — ignore them.
- Frontend: follow `frontend/AGENTS.md` — this is Next.js 16, read `node_modules/next/dist/docs/` before writing code if uncertain. Tailwind v4 theme tokens from `app/globals.css`: `bg-surface`, `bg-panel`, `bg-panel-hover`, `text-text-primary`, `text-text-secondary`, `border-border`, `bg-accent`, `text-user-text`, etc.
- Frontend has no test infra — verification is manual (`npm run dev` smoke) + `npm run lint`.

---

### Task 1: AdminStore (DB layer)

**Files:**
- Create: `backend/src/api/admin_store.py`
- Test: `backend/tests/test_admin_store.py`

**Interfaces:**
- Produces: `AdminStore(db_path: str)` with async `connect()`, `close()`, `seed_default_skill()`, `list_skills() -> list[SkillInfo]`, `get_skill(name) -> SkillInfo | None`, `create_skill(name, description, content)` (raises `ValueError` on duplicate), `update_skill(name, description, content)` (raises `KeyError` if missing), `delete_skill(name)` (raises `KeyError` if missing), `get_openapi_config() -> OpenApiConfig`, `save_openapi_config(spec_content, base_url, token, enabled)`. Dataclass `OpenApiConfig(spec_content: str = "", base_url: str = "", token: str = "", enabled: bool = False, updated_at: str = "")`. Constant `DEFAULT_SKILL = ("code-review", "<description>", "<body>")`. Skill content stored WITHOUT frontmatter (body only).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_admin_store.py`:

```python
import asyncio

import pytest

from src.api.admin_store import AdminStore, DEFAULT_SKILL


@pytest.fixture
def store(tmp_path):
    s = AdminStore(str(tmp_path / "admin.db"))
    asyncio.run(s.connect())
    yield s
    asyncio.run(s.close())


def test_seed_default_skill_when_empty(store):
    asyncio.run(store.seed_default_skill())
    skills = asyncio.run(store.list_skills())
    assert [s.name for s in skills] == ["code-review"]
    assert skills[0].description == DEFAULT_SKILL[1]
    # second run does not duplicate
    asyncio.run(store.seed_default_skill())
    assert len(asyncio.run(store.list_skills())) == 1


def test_skill_crud(store):
    asyncio.run(store.create_skill("demo", "Demo skill", "# Steps\n1. Do it"))
    skills = asyncio.run(store.list_skills())
    assert [s.name for s in skills] == ["demo"]

    loaded = asyncio.run(store.get_skill("demo"))
    assert loaded is not None and loaded.content == "# Steps\n1. Do it"

    with pytest.raises(ValueError):
        asyncio.run(store.create_skill("demo", "dup", "x"))

    asyncio.run(store.update_skill("demo", "New desc", "# New"))
    assert asyncio.run(store.get_skill("demo")).description == "New desc"

    with pytest.raises(KeyError):
        asyncio.run(store.update_skill("nope", "d", "c"))
    with pytest.raises(KeyError):
        asyncio.run(store.delete_skill("nope"))

    asyncio.run(store.delete_skill("demo"))
    assert asyncio.run(store.get_skill("demo")) is None


def test_openapi_config_roundtrip(store):
    cfg = asyncio.run(store.get_openapi_config())
    assert cfg.spec_content == "" and cfg.enabled is False

    asyncio.run(
        store.save_openapi_config('{"paths": {}}', "http://x", "tok123", True)
    )
    cfg = asyncio.run(store.get_openapi_config())
    assert cfg.spec_content == '{"paths": {}}'
    assert cfg.base_url == "http://x" and cfg.token == "tok123" and cfg.enabled is True

    asyncio.run(store.save_openapi_config("", "", "", False))
    cfg = asyncio.run(store.get_openapi_config())
    assert cfg.enabled is False and cfg.spec_content == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_admin_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.admin_store'`

- [ ] **Step 3: Write minimal implementation**

`backend/src/api/admin_store.py`:

```python
"""SQLite-backed persistence for skills and OpenAPI configuration."""

from dataclasses import dataclass

import aiosqlite

from src.skills.registry import SkillInfo

DEFAULT_SKILL = (
    "code-review",
    "Review code systematically for correctness, security, and maintainability before reporting findings.",
    "# Code Review Skill\n\n"
    "Follow these steps when the user asks for a code review:\n\n"
    "1. Read the file(s) under review.\n"
    "2. Check for: correctness bugs, security issues (injection, secrets, auth), "
    "maintainability (dead code, unclear names).\n"
    "3. List findings as `[severity] file:line — issue` (severity: HIGH/MED/LOW).\n"
    "4. For each HIGH finding, propose a concrete fix.\n"
    "5. End with an overall verdict (Approved / Needs changes).",
)


@dataclass
class OpenApiConfig:
    spec_content: str = ""
    base_url: str = ""
    token: str = ""
    enabled: bool = False
    updated_at: str = ""


class AdminStore:
    """Persist skills and OpenAPI config in SQLite (same pattern as ChatStore)."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS openapi_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                spec_content TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT '',
                token TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def seed_default_skill(self) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute("SELECT COUNT(*) FROM skills")
        (count,) = await cursor.fetchone()
        await cursor.close()
        if count == 0:
            name, description, content = DEFAULT_SKILL
            await self._conn.execute(
                "INSERT INTO skills (name, description, content) VALUES (?, ?, ?)",
                (name, description, content),
            )
            await self._conn.commit()

    async def list_skills(self) -> list[SkillInfo]:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "SELECT name, description, content FROM skills ORDER BY name"
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            SkillInfo(name=r[0], description=r[1], path=None)
            for r in rows
        ]

    async def get_skill(self, name: str) -> SkillInfo | None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "SELECT name, description, content FROM skills WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return SkillInfo(name=row[0], description=row[1], path=None)

    async def create_skill(self, name: str, description: str, content: str) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        try:
            await self._conn.execute(
                "INSERT INTO skills (name, description, content) VALUES (?, ?, ?)",
                (name, description, content),
            )
            await self._conn.commit()
        except aiosqlite.IntegrityError as exc:
            raise ValueError(f"Skill already exists: {name}") from exc

    async def update_skill(self, name: str, description: str, content: str) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "UPDATE skills SET description = ?, content = ?, "
            "updated_at = datetime('now') WHERE name = ?",
            (description, content, name),
        )
        await self._conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Skill not found: {name}")

    async def delete_skill(self, name: str) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "DELETE FROM skills WHERE name = ?", (name,)
        )
        await self._conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Skill not found: {name}")

    async def get_openapi_config(self) -> OpenApiConfig:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "SELECT spec_content, base_url, token, enabled, updated_at "
            "FROM openapi_config WHERE id = 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return OpenApiConfig()
        return OpenApiConfig(
            spec_content=row[0],
            base_url=row[1],
            token=row[2],
            enabled=bool(row[3]),
            updated_at=row[4],
        )

    async def save_openapi_config(
        self, spec_content: str, base_url: str, token: str, enabled: bool
    ) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        await self._conn.execute(
            """
            INSERT INTO openapi_config (id, spec_content, base_url, token, enabled, updated_at)
            VALUES (1, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                spec_content = excluded.spec_content,
                base_url = excluded.base_url,
                token = excluded.token,
                enabled = excluded.enabled,
                updated_at = datetime('now')
            """,
            (spec_content, base_url, token, int(enabled)),
        )
        await self._conn.commit()
```

Note: `src/skills/registry.py` must keep exporting `SkillInfo` with `path: Path | None = None` (Task 2 makes `path` optional). Importing `SkillInfo` from registry inside admin_store is fine (registry will not import admin_store at module top — see Task 2; admin_store imports only `SkillInfo` from it).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_admin_store.py -q`
Expected: PASS — 3 passed. (This task also requires Task 2's registry change for `path=None`; if Task 2 is not yet done, `SkillInfo` still has `path: Path` — the dataclass accepts `None` positionally anyway since `path` is the third field with no type enforcement at runtime. Tests pass either way.)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/admin_store.py backend/tests/test_admin_store.py
git commit -m "feat(api): add AdminStore for skills and openapi config persistence"
```

---

### Task 2: DB-backed SkillRegistry (async)

**Files:**
- Modify: `backend/src/skills/registry.py` (full rewrite)
- Modify: `backend/src/skills/tools.py` (async def)
- Modify: `backend/src/graph/builder.py` (one `await`)
- Modify: `backend/src/config/settings.py` (remove `skills_dir`)
- Modify: `backend/tests/test_settings.py` (remove skills_dir assertion)
- Rewrite: `backend/tests/test_skills_registry.py`
- Rewrite: `backend/tests/test_skills_tools.py`
- Delete: `backend/skills/code-review/SKILL.md` (and empty dir)

**Interfaces:**
- Consumes: `AdminStore` from Task 1 (`list_skills`, `get_skill`, `connect`).
- Produces: `parse_frontmatter(text) -> dict` (exported), `SkillInfo(name, description, path=None)`, `SkillRegistry(store_factory: Callable[[], AdminStore])` with async `list_skills()`, `load(name)` (raises `KeyError`), `get_skill_registry()` (@lru_cache), async `build_skills_discovery() -> str`. Consumers: `src/skills/tools.py` awaits them; `builder.py` awaits `build_skills_discovery()`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_skills_registry.py` (full rewrite):

```python
import asyncio

import pytest

from src.api.admin_store import AdminStore
from src.skills.registry import build_skills_discovery, parse_frontmatter


def _reg(tmp_path):
    """Return a registry wired to a fresh DB."""
    from src.skills.registry import get_skill_registry

    import src.config.settings as settings_module

    settings_module.settings.db_path = str(tmp_path / "skills.db")
    get_skill_registry.cache_clear()
    return get_skill_registry()


def test_list_skills_sorted_and_load(tmp_path):
    reg = _reg(tmp_path)
    store = AdminStore(str(tmp_path / "skills.db"))
    asyncio.run(store.connect())
    asyncio.run(store.create_skill("beta", "B skill", "body-b"))
    asyncio.run(store.create_skill("alpha", "A skill", "body-a"))
    asyncio.run(store.close())

    skills = asyncio.run(reg.list_skills())
    assert [s.name for s in skills] == ["alpha", "beta"]
    assert asyncio.run(reg.load("alpha")) == "body-a"


def test_load_unknown_skill_raises_key_error(tmp_path):
    reg = _reg(tmp_path)
    with pytest.raises(KeyError, match="demo"):
        asyncio.run(reg.load("demo"))


def test_build_skills_discovery(tmp_path):
    reg = _reg(tmp_path)
    store = AdminStore(str(tmp_path / "skills.db"))
    asyncio.run(store.connect())
    asyncio.run(store.create_skill("demo", "Demo skill", "body"))
    asyncio.run(store.close())
    assert asyncio.run(build_skills_discovery()) == "demo: Demo skill"


def test_parse_frontmatter_handles_malformed():
    assert parse_frontmatter("no frontmatter") == {}
    assert parse_frontmatter("---\nname: x\n---\nbody") == {"name": "x"}
    assert parse_frontmatter("---\n{{{\n---\nbody") == {}
```

`backend/tests/test_skills_tools.py` (full rewrite):

```python
import asyncio

from src.skills.tools import list_skills, load_skill


def _seed(tmp_path, name="demo", description="Demo skill", content="# Demo"):
    import src.config.settings as settings_module
    from src.api.admin_store import AdminStore
    from src.skills.registry import get_skill_registry

    settings_module.settings.db_path = str(tmp_path / "skills.db")
    get_skill_registry.cache_clear()
    store = AdminStore(str(tmp_path / "skills.db"))
    asyncio.run(store.connect())
    asyncio.run(store.create_skill(name, description, content))
    asyncio.run(store.close())


def test_list_skills_formats(tmp_path):
    _seed(tmp_path)
    assert asyncio.run(list_skills.ainvoke({})) == "demo: Demo skill"


def test_load_skill_returns_content(tmp_path):
    _seed(tmp_path, content="# Steps\n1. Do X")
    assert asyncio.run(load_skill.ainvoke({"name": "demo"})) == "# Steps\n1. Do X"


def test_load_unknown_skill_returns_error_string(tmp_path):
    assert asyncio.run(load_skill.ainvoke({"name": "nope"})) == "Skill not found: nope"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_skills_registry.py tests/test_skills_tools.py -q`
Expected: FAIL (registry still file-based — `list_skills` is sync, `parse_frontmatter` import may pass, `asyncio.run(reg.list_skills())` errors "coroutine was never awaited" or AttributeError).

- [ ] **Step 3: Rewrite the registry, tools, builder, settings**

`backend/src/skills/registry.py` (full rewrite):

```python
"""DB-backed skill registry (skills stored via AdminStore, not files)."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import yaml

from src.config.settings import settings


@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path | None = None


def parse_frontmatter(text: str) -> dict:
    """Return frontmatter dict, or {} if missing/malformed."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


class SkillRegistry:
    """Expose skills stored in the DB (via AdminStore)."""

    def __init__(self, store_factory: Callable[[], "AdminStore"]) -> None:
        self._store_factory = store_factory
        self._store: "AdminStore | None" = None

    async def _ensure_store(self) -> "AdminStore":
        if self._store is None:
            from src.api.admin_store import AdminStore

            self._store = self._store_factory()
            await self._store.connect()
        return self._store

    async def list_skills(self) -> list[SkillInfo]:
        store = await self._ensure_store()
        return await store.list_skills()

    async def load(self, name: str) -> str:
        store = await self._ensure_store()
        skill = await store.get_skill(name)
        if skill is None:
            raise KeyError(f"Skill not found: {name}")
        return skill.content


def _default_store_factory() -> "AdminStore":
    from src.api.admin_store import AdminStore

    return AdminStore(settings.db_path)


@lru_cache
def get_skill_registry() -> SkillRegistry:
    """Cached for the process lifetime; DB queries run per call, so new/edited
    skills are visible immediately. Point at a different DB via settings.db_path
    and call get_skill_registry.cache_clear()."""
    return SkillRegistry(_default_store_factory)


async def build_skills_discovery() -> str:
    """Discovery section for the system prompt: 'name: description' lines."""
    skills = await get_skill_registry().list_skills()
    return "\n".join(f"{s.name}: {s.description}" for s in skills)
```

`backend/src/skills/tools.py` — change both tools to async:

```python
from src.skills.registry import build_skills_discovery, get_skill_registry
from src.tools.registry import register_tool
from langchain_core.tools import tool


@register_tool(group="skills")
@tool
async def list_skills() -> str:
    """List available skills as 'name: description' lines."""
    discovery = await build_skills_discovery()
    return discovery if discovery else "Không có skill nào."


@register_tool(group="skills")
@tool
async def load_skill(name: str) -> str:
    """Load a skill's full instructions by name. Returns the skill body."""
    try:
        return await get_skill_registry().load(name)
    except KeyError:
        return f"Skill not found: {name}"
```

`backend/src/graph/builder.py` — inside `agent_node`, change the line building the skills section:

```python
        skills_section = await build_skills_discovery()
```

(If the current line is `skills_section = build_skills_discovery()`, replace it with the awaited version. Nothing else in builder.py changes.)

`backend/src/config/settings.py` — delete the `# Skills` block:

```python
    # Skills
    skills_dir: str = "skills"
```

`backend/tests/test_settings.py` — in `test_openapi_and_skills_settings_defaults`, remove the line `assert settings.skills_dir == "skills"`.

Delete the retired file-based skill:

```bash
rm -rf backend/skills
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_skills_registry.py tests/test_skills_tools.py tests/test_settings.py tests/test_admin_store.py -q`
Expected: PASS (3 + 3 + 5 + 3). Then full suite: `.venv/bin/python -m pytest -q` — expected 72 passed (unchanged count: 3 new registry + 3 tools + 3 admin_store, minus nothing — skills_registry was 5, now 4; tools was 3, now 3; net +2 vs previous 72? If the count differs, report the actual number; the requirement is FULL SUITE GREEN).

- [ ] **Step 5: Commit**

```bash
git add backend/src/skills/backend/src/graph/builder.py backend/src/config/settings.py backend/tests/test_skills_registry.py backend/tests/test_skills_tools.py backend/tests/test_settings.py
git commit -m "refactor(skills): make skill registry DB-backed via AdminStore"
```

(If `git add` fails on the `src/skills/` path, add `backend/src/skills/` explicitly — the deleted file needs `git add -A backend/skills` or `git rm` to stage the deletion: use `git add -A backend/skills backend/src/graph/builder.py ...`.)

---

### Task 3: Admin API routes + wiring

**Files:**
- Create: `backend/src/api/routes/admin.py`
- Modify: `backend/src/api/routes/__init__.py` (add import)
- Modify: `backend/src/api/main.py` (lifespan store + router)
- Test: `backend/tests/test_admin_routes.py`

**Interfaces:**
- Consumes: `AdminStore` (Task 1), `build_graph(settings)` from `src.graph.builder`, `parse_frontmatter` not needed here.
- Produces: routes `GET /api/v1/admin/config`, `PUT /api/v1/admin/openapi`, `POST /api/v1/admin/skills`, `PUT /api/v1/admin/skills/{name}`, `DELETE /api/v1/admin/skills/{name}`, `POST /api/v1/admin/reload`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_admin_routes.py`:

```python
import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config.settings import Settings

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {"operationId": "User_findAll"},
            "post": {"operationId": "User_create"},
        },
        "/users/{id}": {"delete": {"operationId": "User_delete"}},
    },
}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    db = tmp_path_factory.mktemp("admin") / "test.db"
    return create_app(
        Settings(
            openai_api_key="sk-test",
            tavily_api_key="tvly-test",
            langsmith_api_key="ls-test",
            db_path=str(db),
        )
    )


def test_config_defaults_seeded(app):
    with TestClient(app) as client:
        res = client.get("/api/v1/admin/config")
        assert res.status_code == 200
        data = res.json()
        assert data["openapi"]["enabled"] is False
        assert data["openapi"]["token_masked"] == ""
        assert [s["name"] for s in data["skills"]] == ["code-review"]


def test_save_openapi_valid_and_masked(app):
    with TestClient(app) as client:
        res = client.put(
            "/api/v1/admin/openapi",
            json={
                "spec_content": json.dumps(SPEC),
                "base_url": "http://api.test",
                "token": "sk-abcdef123456",
                "enabled": True,
            },
        )
        assert res.status_code == 200

        data = client.get("/api/v1/admin/config").json()
        assert data["openapi"]["enabled"] is True
        assert data["openapi"]["base_url"] == "http://api.test"
        assert data["openapi"]["token_masked"] == "sk****3456"
        assert data["openapi"]["spec_title"] == "Test API"
        assert data["openapi"]["endpoint_count"] == 3


def test_save_openapi_invalid(app):
    with TestClient(app) as client:
        res = client.put(
            "/api/v1/admin/openapi",
            json={"spec_content": "not json", "enabled": True},
        )
        assert res.status_code == 400

        res = client.put(
            "/api/v1/admin/openapi",
            json={"spec_content": json.dumps({"paths": {}}), "enabled": True},
        )
        assert res.status_code == 400


def test_skills_crud(app):
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/admin/skills",
            json={"name": "demo", "description": "Demo skill", "content": "# Demo"},
        )
        assert res.status_code == 200

        res = client.post(
            "/api/v1/admin/skills",
            json={"name": "demo", "description": "dup", "content": "x"},
        )
        assert res.status_code == 409

        res = client.post(
            "/api/v1/admin/skills",
            json={"name": "Bad Name!", "description": "d", "content": "c"},
        )
        assert res.status_code == 400

        res = client.put(
            "/api/v1/admin/skills/demo",
            json={"description": "Updated", "content": "# New"},
        )
        assert res.status_code == 200
        skills = client.get("/api/v1/admin/config").json()["skills"]
        assert {"name": "demo", "description": "Updated"} in skills

        assert client.put(
            "/api/v1/admin/skills/nope",
            json={"description": "d", "content": "c"},
        ).status_code == 404

        assert client.delete("/api/v1/admin/skills/demo").status_code == 200
        assert client.delete("/api/v1/admin/skills/demo").status_code == 404


def test_reload_swaps_graph(app):
    with TestClient(app) as client:
        old_graph = app.state.graph
        res = client.put(
            "/api/v1/admin/openapi",
            json={"spec_content": json.dumps(SPEC), "base_url": "http://api.test", "token": "tok", "enabled": True},
        )
        assert res.status_code == 200

        res = client.post("/api/v1/admin/reload")
        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["openapi_enabled"] is True
        assert data["endpoint_count"] == 3
        assert data["skills_count"] >= 1
        assert app.state.graph is not old_graph
        assert app.state.settings.openapi_spec_path is not None


def test_reload_disabled_removes_openapi(app):
    with TestClient(app) as client:
        client.put(
            "/api/v1/admin/openapi",
            json={"spec_content": json.dumps(SPEC), "base_url": "http://api.test", "token": "tok", "enabled": True},
        )
        client.post("/api/v1/admin/reload")
        assert app.state.settings.openapi_spec_path is not None

        client.put(
            "/api/v1/admin/openapi",
            json={"spec_content": "", "base_url": "", "token": "", "enabled": False},
        )
        res = client.post("/api/v1/admin/reload")
        assert res.status_code == 200
        assert res.json()["openapi_enabled"] is False
        assert app.state.settings.openapi_spec_path is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py -q`
Expected: FAIL — 404 on `/api/v1/admin/config` (router not registered).

- [ ] **Step 3: Write the routes and wire main.py**

`backend/src/api/routes/admin.py`:

```python
"""Admin routes: OpenAPI config and skill management."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])

SKILL_NAME_RE = re.compile(r"^[a-z0-9-]+$")
OPENAPI_METHODS = {"get", "post", "put", "patch", "delete"}


def count_operations(spec: dict) -> int:
    """Count GET/POST/PUT/PATCH/DELETE operations across paths (same filter as the loader)."""
    total = 0
    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        total += sum(1 for m in path_item if str(m).lower() in OPENAPI_METHODS)
    return total


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 6:
        return "****"
    return f"{token[:2]}****{token[-4:]}"


class OpenApiPayload(BaseModel):
    spec_content: str
    base_url: str = ""
    token: str = ""
    enabled: bool = False


class SkillPayload(BaseModel):
    name: str
    description: str
    content: str


class SkillUpdatePayload(BaseModel):
    description: str
    content: str


@router.get("/config")
async def get_config(request: Request) -> dict:
    store = request.app.state.admin_store
    cfg = await store.get_openapi_config()
    skills = await store.list_skills()
    spec_title = ""
    endpoint_count = 0
    if cfg.spec_content:
        try:
            parsed = json.loads(cfg.spec_content)
            spec_title = str(parsed.get("info", {}).get("title", ""))
            endpoint_count = count_operations(parsed)
        except json.JSONDecodeError:
            pass
    return {
        "openapi": {
            "enabled": cfg.enabled,
            "base_url": cfg.base_url,
            "token_masked": mask_token(cfg.token),
            "spec_title": spec_title,
            "endpoint_count": endpoint_count,
        },
        "skills": [{"name": s.name, "description": s.description} for s in skills],
    }


@router.put("/openapi")
async def save_openapi(payload: OpenApiPayload, request: Request) -> dict:
    store = request.app.state.admin_store
    if payload.enabled:
        try:
            spec = json.loads(payload.spec_content)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, f"invalid JSON: {exc}") from exc
        if not isinstance(spec, dict) or count_operations(spec) == 0:
            raise HTTPException(400, "no operations found in spec")
    await store.save_openapi_config(
        payload.spec_content, payload.base_url, payload.token, payload.enabled
    )
    return {"ok": True}


@router.post("/skills")
async def create_skill(payload: SkillPayload, request: Request) -> dict:
    if not SKILL_NAME_RE.fullmatch(payload.name) or len(payload.name) > 64:
        raise HTTPException(400, "name must match ^[a-z0-9-]+$ and be at most 64 chars")
    if not payload.description.strip() or not payload.content.strip():
        raise HTTPException(400, "description and content are required")
    store = request.app.state.admin_store
    try:
        await store.create_skill(payload.name, payload.description.strip(), payload.content)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True}


@router.put("/skills/{name}")
async def update_skill(name: str, payload: SkillUpdatePayload, request: Request) -> dict:
    if not payload.description.strip() or not payload.content.strip():
        raise HTTPException(400, "description and content are required")
    store = request.app.state.admin_store
    try:
        await store.update_skill(name, payload.description.strip(), payload.content)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True}


@router.delete("/skills/{name}")
async def delete_skill(name: str, request: Request) -> dict:
    store = request.app.state.admin_store
    try:
        await store.delete_skill(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True}


@router.post("/reload")
async def reload_graph(request: Request) -> dict:
    app = request.app
    store = app.state.admin_store
    cfg = await store.get_openapi_config()
    settings = app.state.settings

    if cfg.enabled and cfg.spec_content:
        spec_path = Path(settings.db_path).parent / "imported_openapi.json"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(cfg.spec_content, encoding="utf-8")
        settings.openapi_spec_path = str(spec_path)
        settings.openapi_base_url = cfg.base_url or None
        settings.openapi_token = cfg.token or None
    else:
        settings.openapi_spec_path = None
        settings.openapi_base_url = None
        settings.openapi_token = None

    from src.graph.builder import build_graph

    new_graph = await build_graph(settings)
    old_graph = app.state.graph
    checkpointer = getattr(old_graph, "checkpointer", None)
    conn = getattr(checkpointer, "conn", None)
    if conn is not None:
        await conn.close()
    app.state.graph = new_graph

    parsed = json.loads(cfg.spec_content) if cfg.spec_content else {}
    return {
        "ok": True,
        "openapi_enabled": settings.openapi_spec_path is not None,
        "endpoint_count": count_operations(parsed) if parsed else 0,
        "skills_count": len(await store.list_skills()),
    }
```

`backend/src/api/routes/__init__.py`:

```python
from src.api.routes import admin, chat, threads
```

`backend/src/api/main.py` — add imports and lifespan wiring:

```python
from src.api.admin_store import AdminStore
from src.api.routes import admin, chat, threads
```

In `lifespan`, after the `chat_store` block:

```python
    admin_store = AdminStore(app.state.settings.db_path)
    await admin_store.connect()
    await admin_store.seed_default_skill()
    app.state.admin_store = admin_store
```

and in `finally`, after `await chat_store.close()`:

```python
        await admin_store.close()
```

Register the router after the other include_router calls:

```python
    app.include_router(admin.router, prefix="/api/v1")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_admin_routes.py -q`
Expected: PASS — 6 passed. Then full suite: `.venv/bin/python -m pytest -q` — full suite green (report the count).

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/admin.py backend/src/api/routes/__init__.py backend/src/api/main.py backend/tests/test_admin_routes.py
git commit -m "feat(api): add admin routes for openapi config, skills, and graph reload"
```

---

### Task 4: Frontend admin page

**Files:**
- Modify: `frontend/lib/api.ts` (add admin API functions)
- Create: `frontend/app/admin/page.tsx`
- Modify: `frontend/app/page.tsx` (Admin link)

**Interfaces:**
- Consumes: backend routes from Task 3.
- Produces: `getAdminConfig()`, `saveOpenApiConfig(payload)`, `reloadGraph()`, `createSkill(payload)`, `updateSkill(name, payload)`, `deleteSkill(name)` in `lib/api.ts`; `/admin` page.

Read `frontend/AGENTS.md` first (Next.js 16 — check `node_modules/next/dist/docs/` for App Router conventions if needed). This page is user-facing; polish the styling with the Tailwind v4 theme tokens from `app/globals.css` (`bg-surface`, `bg-panel`, `bg-panel-hover`, `bg-panel-active`, `border-border`, `border-border-strong`, `bg-accent`, `bg-accent-hover`, `text-text-primary`, `text-text-secondary`, `text-text-tertiary`, `text-text-on-dark`, `text-text-on-dark-muted`, `bg-success`, `bg-error`, `bg-error-bg`).

- [ ] **Step 1: Add API functions to `frontend/lib/api.ts`**

Append:

```ts
// ---- Admin ----

export interface AdminOpenApiStatus {
  enabled: boolean;
  base_url: string;
  token_masked: string;
  spec_title: string;
  endpoint_count: number;
}

export interface AdminSkillSummary {
  name: string;
  description: string;
}

export interface AdminConfig {
  openapi: AdminOpenApiStatus;
  skills: AdminSkillSummary[];
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body?.detail ?? `HTTP ${res.status}`;
  } catch {
    return `HTTP ${res.status}`;
  }
}

export async function getAdminConfig(): Promise<AdminConfig> {
  const res = await fetch(`${API_URL}/admin/config`);
  if (!res.ok) throw new Error(await readDetail(res));
  return res.json();
}

export async function saveOpenApiConfig(payload: {
  spec_content: string;
  base_url: string;
  token: string;
  enabled: boolean;
}): Promise<void> {
  const res = await fetch(`${API_URL}/admin/openapi`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readDetail(res));
}

export async function reloadGraph(): Promise<{
  ok: boolean;
  openapi_enabled: boolean;
  endpoint_count: number;
  skills_count: number;
}> {
  const res = await fetch(`${API_URL}/admin/reload`, { method: "POST" });
  if (!res.ok) throw new Error(await readDetail(res));
  return res.json();
}

export async function createSkill(payload: {
  name: string;
  description: string;
  content: string;
}): Promise<void> {
  const res = await fetch(`${API_URL}/admin/skills`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readDetail(res));
}

export async function updateSkill(
  name: string,
  payload: { description: string; content: string }
): Promise<void> {
  const res = await fetch(`${API_URL}/admin/skills/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readDetail(res));
}

export async function deleteSkill(name: string): Promise<void> {
  const res = await fetch(`${API_URL}/admin/skills/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await readDetail(res));
}
```

- [ ] **Step 2: Create `frontend/app/admin/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AdminConfig,
  createSkill,
  deleteSkill,
  getAdminConfig,
  reloadGraph,
  saveOpenApiConfig,
  updateSkill,
} from "@/lib/api";

type SkillForm = { name: string; description: string; content: string };
const EMPTY_FORM: SkillForm = { name: "", description: "", content: "" };

function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="rounded-lg bg-error-bg px-4 py-2 text-sm text-error">
      {message}
    </div>
  );
}

function SuccessBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="rounded-lg bg-success-bg px-4 py-2 text-sm text-success">
      {message}
    </div>
  );
}

export default function AdminPage() {
  const [config, setConfig] = useState<AdminConfig | null>(null);
  const [specContent, setSpecContent] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [token, setToken] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [form, setForm] = useState<SkillForm>(EMPTY_FORM);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setConfig(await getAdminConfig());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleSaveOpenApi() {
    setError(""); setNotice(""); setBusy(true);
    try {
      await saveOpenApiConfig({ spec_content: specContent, base_url: baseUrl, token, enabled });
      const result = await reloadGraph();
      setNotice(
        `Đã lưu & reload. ${result.openapi_enabled ? `${result.endpoint_count} endpoint API` : "OpenAPI đã tắt"} · ${result.skills_count} skill.`
      );
      setSpecContent(""); setToken("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function handleFile(file: File | undefined) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setSpecContent(String(reader.result ?? ""));
    reader.readAsText(file);
  }

  async function handleSaveSkill() {
    setError(""); setNotice(""); setBusy(true);
    try {
      if (editingName) {
        await updateSkill(editingName, { description: form.description, content: form.content });
      } else {
        await createSkill(form);
      }
      setForm(EMPTY_FORM);
      setEditingName(null);
      setNotice(editingName ? "Đã cập nhật skill." : "Đã tạo skill mới.");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function startEdit(skill: { name: string; description: string }) {
    setEditingName(skill.name);
    setForm({ name: skill.name, description: skill.description, content: "" });
  }

  async function handleDelete(name: string) {
    if (!window.confirm(`Xóa skill "${name}"?`)) return;
    setError(""); setNotice(""); setBusy(true);
    try {
      await deleteSkill(name);
      setNotice(`Đã xóa skill "${name}".`);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col gap-6 overflow-y-auto p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-text-primary">Quản lý Agent</h1>
        <Link href="/" className="text-sm text-accent hover:underline">
          ← Về trang chat
        </Link>
      </div>

      <ErrorBanner message={error} />
      <SuccessBanner message={notice} />

      {/* OpenAPI */}
      <section className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <h2 className="mb-1 text-lg font-semibold text-text-primary">API từ file OpenAPI</h2>
        {config?.openapi.enabled ? (
          <p className="mb-4 text-sm text-text-secondary">
            Đang bật · <span className="font-mono">{config.openapi.spec_title}</span> ·{" "}
            {config.openapi.endpoint_count} endpoint ·{" "}
            <span className="font-mono">{config.openapi.base_url}</span> · token{" "}
            <span className="font-mono">{config.openapi.token_masked}</span>
          </p>
        ) : (
          <p className="mb-4 text-sm text-text-secondary">Chưa bật — agent chưa có tool API.</p>
        )}

        <div className="flex flex-col gap-3">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-text-primary">
            <input
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
            <span className="rounded-lg bg-panel px-3 py-2 text-sm text-text-on-dark hover:bg-panel-hover">
              Chọn file spec (.json)
            </span>
          </label>
          <textarea
            value={specContent}
            onChange={(e) => setSpecContent(e.target.value)}
            placeholder="Hoặc dán nội dung spec JSON vào đây…"
            rows={6}
            className="w-full rounded-lg border border-border p-2 font-mono text-xs text-text-primary focus:border-accent"
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="Base URL, VD: http://localhost:3003"
              className="rounded-lg border border-border p-2 text-sm text-text-primary focus:border-accent"
            />
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Token (JWT) — để trống nếu không đổi"
              className="rounded-lg border border-border p-2 text-sm text-text-primary focus:border-accent"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-text-primary">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            Bật tool API
          </label>
          <button
            onClick={handleSaveOpenApi}
            disabled={busy}
            className="self-start rounded-lg bg-accent px-4 py-2 text-sm font-medium text-user-text hover:bg-accent-hover disabled:opacity-50"
          >
            Lưu & Reload
          </button>
        </div>
      </section>

      {/* Skills */}
      <section className="rounded-xl border border-border bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-text-primary">Skills (sổ tay hướng dẫn)</h2>

        <ul className="mb-5 flex flex-col gap-2">
          {config?.skills.map((s) => (
            <li key={s.name} className="flex items-start justify-between gap-3 rounded-lg bg-surface p-3">
              <div>
                <p className="font-mono text-sm font-medium text-text-primary">{s.name}</p>
                <p className="text-sm text-text-secondary">{s.description}</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  onClick={() => startEdit(s)}
                  className="rounded-lg border border-border px-3 py-1 text-xs text-text-primary hover:bg-surface-alt"
                >
                  Sửa
                </button>
                <button
                  onClick={() => handleDelete(s.name)}
                  className="rounded-lg border border-border px-3 py-1 text-xs text-error hover:bg-error-bg"
                >
                  Xóa
                </button>
              </div>
            </li>
          ))}
          {config && config.skills.length === 0 && (
            <li className="text-sm text-text-secondary">Chưa có skill nào.</li>
          )}
        </ul>

        <h3 className="mb-2 text-sm font-semibold text-text-primary">
          {editingName ? `Sửa skill: ${editingName}` : "Tạo skill mới"}
        </h3>
        <div className="flex flex-col gap-3">
          {!editingName && (
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Tên skill (chữ thường + gạch ngang, VD: viet-email)"
              className="rounded-lg border border-border p-2 text-sm text-text-primary focus:border-accent"
            />
          )}
          <input
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Mô tả ngắn — agent dựa vào dòng này để biết khi nào dùng skill"
            className="rounded-lg border border-border p-2 text-sm text-text-primary focus:border-accent"
          />
          <textarea
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            placeholder={"Nội dung hướng dẫn (body, không cần frontmatter). VD:\n# Quy trình\n1. Bước một…"}
            rows={6}
            className="w-full rounded-lg border border-border p-2 font-mono text-xs text-text-primary focus:border-accent"
          />
          <div className="flex gap-2">
            <button
              onClick={handleSaveSkill}
              disabled={busy}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-user-text hover:bg-accent-hover disabled:opacity-50"
            >
              {editingName ? "Lưu thay đổi" : "Tạo skill"}
            </button>
            {editingName && (
              <button
                onClick={() => { setEditingName(null); setForm(EMPTY_FORM); }}
                className="rounded-lg border border-border px-4 py-2 text-sm text-text-primary hover:bg-surface-alt"
              >
                Hủy
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Add the Admin link to `frontend/app/page.tsx`**

Replace the outer `<div className="flex h-full">` with `<div className="relative flex h-full">` and add, as the first child:

```tsx
      <Link
        href="/admin"
        className="absolute right-3 top-3 z-10 rounded-lg bg-panel px-3 py-1.5 text-xs font-medium text-text-on-dark hover:bg-panel-hover"
      >
        Admin
      </Link>
```

Add `import Link from "next/link";` at the top of the file (before `import { useState } from "react";`).

- [ ] **Step 4: Verify**

Run: `npm run lint` from `frontend/` — no errors (or only pre-existing ones). Then `npm run dev` (or `npm run build`) and manual smoke:
1. Open `http://localhost:3000/admin` — status card shows "Chưa bật", skills list shows `code-review`.
2. Select the real spec file (`backend/specs/ẹ ẹ ẹ.json`), fill base URL + token, check "Bật tool API", click "Lưu & Reload" → notice shows endpoint count (45).
3. Backend log shows no exception; `curl http://localhost:8000/api/v1/admin/config` shows enabled + masked token.
4. Create a skill via the form → appears in the list. Delete it → gone. Create one and verify the agent discovers it: open `/` chat, ask "bạn có những skill nào" → lists it.
5. Uncheck "Bật tool API", reload → status "Chưa bật".

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/app/admin/page.tsx frontend/app/page.tsx
git commit -m "feat(web): add admin page for openapi config and skill management"
```

---

### Task 5: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run from `backend/`: `.venv/bin/python -m pytest -q`
Expected: full suite green (report the count — baseline 72 + admin_store 3 + admin_routes 6 + registry/tools rebalance).

- [ ] **Step 2: Backend boot + reload smoke (no restart)**

From `backend/`:

```bash
OPENAPI_SPEC_PATH='' .venv/bin/python -m uvicorn src.api.main:app --port 8000 &
sleep 3
curl -s http://localhost:8000/api/v1/admin/config | head -c 300
```

Expected: JSON with `"enabled": false` and skills including `code-review`. Then:

```bash
curl -s -X POST http://localhost:8000/api/v1/admin/reload | head -c 200
curl -s -X PUT http://localhost:8000/api/v1/admin/openapi \
  -H 'Content-Type: application/json' \
  -d '{"spec_content":"{\"paths\":{\"/ping\":{\"get\":{\"operationId\":\"Ping_get\"}}}}","base_url":"http://x","token":"t","enabled":true}' | head -c 200
curl -s -X POST http://localhost:8000/api/v1/admin/reload | head -c 200
```

Expected: reload returns `"endpoint_count": 1` after the PUT. Kill the uvicorn process afterwards.

- [ ] **Step 3: Tree check**

Run: `git status --short` — only intended files; `data/` and `backend/specs/` remain gitignored; no stray files.

- [ ] **Step 4: Commit any leftover doc/ledger updates**

```bash
git add -A docs .superpowers 2>/dev/null || true
git commit -m "docs: update admin config ui plan" 2>/dev/null || true
```
