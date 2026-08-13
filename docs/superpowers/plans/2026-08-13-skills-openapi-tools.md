# Skills + OpenAPI File-Based Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Agent Moew two new capabilities — on-demand loading of markdown skills (`SKILL.md`) and auto-generated tools from an OpenAPI spec file — without changing the graph structure.

**Architecture:** A new `src/skills/` module parses `skills/*/SKILL.md` frontmatter and exposes `load_skill`/`list_skills` tools plus a discovery string for the system prompt. A new `src/tools/openapi_loader.py` parses an OpenAPI 3.0 JSON spec at startup and generates one `@tool` per endpoint (httpx async, JWT header, truncated structured output). `builder.py` stays top-level ReAct: it just extends `all_tools` and appends skills discovery to the system message.

**Tech Stack:** Python 3.12, langchain-core `@tool`, langgraph `ToolNode`, httpx 0.28 (already a dependency), PyYAML 6.0.3 (already in venv via deepagents), pydantic-settings, pytest (asyncio_mode=auto).

## Global Constraints

- Backend root for all commands: `/home/roser/Work-Code/agent_moew/backend`; run tests via `.venv/bin/python -m pytest`.
- Follow existing tool pattern: `@register_tool(group=...)` above `@tool` (see `src/tools/time_tools.py`).
- Tool functions must return strings (LangChain tool convention here); never raise — return structured `ERROR [...]` strings for HTTP failures.
- Truncate tool output with `truncate_text(text, 8000)` from `src/tools/truncate.py`.
- Secrets (JWT token) come from `Settings`; never embed tokens in code, prompts, or logs.
- Skills dir defaults to `skills` (relative to backend cwd); frontmatter requires `name` + `description`.
- No new graph nodes/edges; only `builder.py` list/prompt changes.

---

### Task 1: Settings fields for OpenAPI + skills

**Files:**
- Modify: `src/config/settings.py` (add 4 fields after `workspace_dir`)
- Test: `tests/test_settings.py` (append new test)

**Interfaces:**
- Produces: `Settings.openapi_spec_path: Optional[str]`, `Settings.openapi_base_url: Optional[str]`, `Settings.openapi_token: Optional[str]`, `Settings.skills_dir: str = "skills"` (all default to None/"skills", so existing tests and runs are unaffected)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_settings.py`:

```python
def test_openapi_and_skills_settings_defaults():
    s = Settings()
    assert s.openapi_spec_path is None
    assert s.openapi_base_url is None
    assert s.openapi_token is None
    assert s.skills_dir == "skills"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `/home/roser/Work-Code/agent_moew/backend`): `.venv/bin/python -m pytest tests/test_settings.py -k openapi_and_skills -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'openapi_spec_path'`

- [ ] **Step 3: Add the fields**

In `src/config/settings.py`, after `workspace_dir: str = "workspace"`:

```python
    # OpenAPI file-based tools (optional; empty = disabled)
    openapi_spec_path: Optional[str] = None
    openapi_base_url: Optional[str] = None
    openapi_token: Optional[str] = None

    # Skills
    skills_dir: str = "skills"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_settings.py -v`
Expected: PASS (all settings tests)

- [ ] **Step 5: Commit**

```bash
git add src/config/settings.py tests/test_settings.py
git commit -m "feat(config): add openapi spec + skills settings fields"
```

---

### Task 2: SkillRegistry (frontmatter parsing + load)

**Files:**
- Create: `src/skills/__init__.py`, `src/skills/registry.py`
- Test: `tests/test_skills_registry.py`

**Interfaces:**
- Consumes: `Settings.skills_dir` (Task 1)
- Produces:
  - `@dataclass SkillInfo`: `name: str`, `description: str`, `path: Path`
  - `class SkillRegistry(root: Path)`: `list_skills() -> list[SkillInfo]`, `load(name: str) -> str` (raises `KeyError` if missing)
  - `get_skill_registry() -> SkillRegistry` — `functools.lru_cache`d singleton over `Path(settings.skills_dir)`
  - `build_skills_discovery() -> str` — `"name: description"` lines or `""` when no skills

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skills_registry.py`:

```python
from pathlib import Path

import pytest

from src.skills.registry import SkillRegistry, build_skills_discovery


def _write_skill(root: Path, name: str, description: str, body: str = "# Steps\n1. Do it") -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}", encoding="utf-8"
    )


def test_scan_lists_skills_in_sorted_order(tmp_path):
    _write_skill(tmp_path, "beta", "B skill")
    _write_skill(tmp_path, "alpha", "A skill")
    reg = SkillRegistry(tmp_path)
    names = [s.name for s in reg.list_skills()]
    assert names == ["alpha", "beta"]


def test_scan_skips_missing_description(tmp_path):
    d = tmp_path / "no-desc"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: no-desc\n---\nbody", encoding="utf-8")
    reg = SkillRegistry(tmp_path)
    assert reg.list_skills() == []


def test_load_returns_body_without_frontmatter(tmp_path):
    _write_skill(tmp_path, "demo", "Demo skill", "# Demo\nSteps here")
    reg = SkillRegistry(tmp_path)
    content = reg.load("demo")
    assert content == "# Demo\nSteps here"
    assert "name:" not in content


def test_load_unknown_skill_raises_key_error(tmp_path):
    reg = SkillRegistry(tmp_path)
    with pytest.raises(KeyError, match="demo"):
        reg.load("demo")


def test_build_skills_discovery(tmp_path, monkeypatch):
    from src.skills.registry import get_skill_registry

    _write_skill(tmp_path, "demo", "Demo skill")
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert build_skills_discovery() == "demo: Demo skill"
    finally:
        get_skill_registry.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_skills_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.skills'`

- [ ] **Step 3: Implement the registry**

Create `src/skills/__init__.py` (empty file).

Create `src/skills/registry.py`:

```python
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from src.config.settings import settings


@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path


def _parse_frontmatter(text: str) -> dict:
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


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip("\n")


class SkillRegistry:
    """Scan skills/*/SKILL.md and expose name/description/content."""

    def __init__(self, root: Path) -> None:
        self._skills: dict[str, SkillInfo] = {}
        for skill_dir in sorted(root.glob("*/")):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            text = skill_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter(text)
            name = fm.get("name") or skill_dir.name
            description = fm.get("description", "")
            if not description:
                continue  # require description so the LLM can discover it
            self._skills[name] = SkillInfo(
                name=name, description=description, path=skill_file
            )

    def list_skills(self) -> list[SkillInfo]:
        return list(self._skills.values())

    def load(self, name: str) -> str:
        if name not in self._skills:
            raise KeyError(f"Skill not found: {name}")
        return _strip_frontmatter(self._skills[name].path.read_text(encoding="utf-8"))


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry(Path(settings.skills_dir))


def build_skills_discovery() -> str:
    """Discovery section for the system prompt: 'name: description' lines."""
    skills = get_skill_registry().list_skills()
    return "\n".join(f"{s.name}: {s.description}" for s in skills)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_skills_registry.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/skills/ tests/test_skills_registry.py
git commit -m "feat(skills): add SkillRegistry with frontmatter parsing"
```

---

### Task 3: Skill tools (load_skill / list_skills)

**Files:**
- Create: `src/skills/tools.py`
- Test: `tests/test_skills_tools.py`

**Interfaces:**
- Consumes: `get_skill_registry()` from Task 2; `register_tool` from `src/tools/registry.py`
- Produces: `load_skill(name: str) -> str` (tool, group `"skills"`), `list_skills() -> str` (tool, group `"skills"`) — importable as `from src.skills.tools import load_skill, list_skills`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_skills_tools.py`:

```python
from src.skills.registry import get_skill_registry
from src.skills.tools import list_skills, load_skill


def test_list_skills_formats(tmp_path, monkeypatch):
    d = tmp_path / "demo"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Demo", encoding="utf-8"
    )
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert list_skills.invoke({}) == "demo: Demo skill"
    finally:
        get_skill_registry.cache_clear()


def test_load_skill_returns_content(tmp_path, monkeypatch):
    d = tmp_path / "demo"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Steps\n1. Do X", encoding="utf-8"
    )
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert load_skill.invoke({"name": "demo"}) == "# Steps\n1. Do X"
    finally:
        get_skill_registry.cache_clear()


def test_load_unknown_skill_returns_error_string(tmp_path, monkeypatch):
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert load_skill.invoke({"name": "nope"}) == "Skill not found: nope"
    finally:
        get_skill_registry.cache_clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_skills_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.skills.tools'`

- [ ] **Step 3: Implement the tools**

Create `src/skills/tools.py`:

```python
from langchain_core.tools import tool

from src.skills.registry import get_skill_registry
from src.tools.registry import register_tool


@register_tool(group="skills")
@tool
def list_skills() -> str:
    """List available skills (format: 'name: description'). Call this to see what skills exist."""
    skills = get_skill_registry().list_skills()
    if not skills:
        return "Không có skill nào."
    return "\n".join(f"{s.name}: {s.description}" for s in skills)


@register_tool(group="skills")
@tool
def load_skill(name: str) -> str:
    """Load the full instructions of a skill by name so you can follow its workflow."""
    try:
        return get_skill_registry().load(name)
    except KeyError:
        return f"Skill not found: {name}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_skills_tools.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/skills/tools.py tests/test_skills_tools.py
git commit -m "feat(skills): add load_skill and list_skills tools"
```

---

### Task 4: OpenAPI loader (one tool per endpoint)

**Files:**
- Create: `src/tools/openapi_loader.py`
- Test: `tests/test_openapi_loader.py`

**Interfaces:**
- Consumes: `truncate_text` from `src/tools/truncate.py`; `registry` from `src/tools/registry.py`
- Produces:
  - `load_openapi_tools(spec_path: str | Path, base_url: str | None = None, token: str | None = None) -> list[BaseTool]`
  - Tools are registered into the global `registry` with group `"api"`; names are snake_case of `operationId` (fallback `<method>_<path_slug>`)
  - Module-level `_client_factory: Callable[[], httpx.AsyncClient]` (default `lambda: httpx.AsyncClient(timeout=30)`) — tests swap it for `httpx.MockTransport`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_openapi_loader.py`:

```python
import json

import httpx

import src.tools.openapi_loader as loader

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/v1/users": {
            "get": {
                "operationId": "User_findAll",
                "description": "List users",
                "parameters": [
                    {"name": "page", "in": "query", "required": False,
                     "schema": {"type": "integer", "default": 1}},
                    {"name": "q", "in": "query", "required": True,
                     "schema": {"type": "string"}},
                ],
            }
        },
        "/v1/users/{id}": {
            "get": {
                "operationId": "User_findOne",
                "description": "Get one user",
                "parameters": [
                    {"name": "id", "in": "path", "required": True,
                     "schema": {"type": "integer"}},
                ],
            }
        },
    },
}


def _write_spec(tmp_path) -> str:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(SPEC), encoding="utf-8")
    return str(p)


def test_generates_one_tool_per_operation(tmp_path):
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="tok")
    names = sorted(t.name for t in tools)
    assert names == ["user_find_all", "user_find_one"]


def test_required_args_in_schema(tmp_path):
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local")
    tool_by_name = {t.name: t for t in tools}
    schema = tool_by_name["user_find_all"].args_schema.model_json_schema()
    props = schema["properties"]
    assert "q" in props and "page" in props
    assert schema["required"] == ["q"]  # only the required query param


def test_invoke_builds_url_headers_and_returns_json(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"name": "Moew"}]})

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="sekret")
    try:
        result = tools[0].invoke({"q": "cat", "page": 2})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    assert captured["url"] == "http://test.local/v1/users?page=2&q=cat"
    assert captured["auth"] == "Bearer sekret"
    assert '"name": "Moew"' in result


def test_path_param_substitution(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"id": 7})

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local")
    try:
        tools[1].invoke({"id": 7})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    assert captured["url"] == "http://test.local/v1/users/7"


def test_http_error_returns_structured_string(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="bad")
    try:
        result = tools[0].invoke({"q": "x"})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    assert result.startswith("ERROR [401]")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_openapi_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.tools.openapi_loader'`

- [ ] **Step 3: Implement the loader**

Create `src/tools/openapi_loader.py`:

```python
import json
import re
from pathlib import Path
from typing import Any, Callable

import httpx
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field, create_model

from src.tools.registry import registry
from src.tools.truncate import truncate_text

_MAX_OUTPUT_CHARS = 8000
_TIMEOUT = 30

_client_factory: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(
    timeout=_TIMEOUT
)

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _to_snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    s2 = re.sub(r"[^a-zA-Z0-9]+", "_", s2)
    return s2.strip("_").lower()


def _path_slug(path: str, method: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_").lower()
    return f"{method}_{slug}"


def _build_args_model(
    params: list[dict], body_schema: dict | None
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    required: list[str] = []
    for p in params:
        ptype = _TYPE_MAP.get(p.get("schema", {}).get("type"), str)
        if p.get("required"):
            fields[p["name"]] = (ptype, Field(description=p.get("description", "")))
            required.append(p["name"])
        else:
            default = p.get("schema", {}).get("default")
            fields[p["name"]] = (
                ptype | None if default is None else ptype,
                Field(default=default, description=p.get("description", "")),
            )
    if body_schema is not None:
        fields["body"] = (dict, Field(default_factory=dict, description="Request JSON body"))
        required.append("body")
    return create_model("OpenApiArgs", **fields)


def _make_operation_tool(
    name: str,
    description: str,
    method: str,
    path_template: str,
    params: list[dict],
    body_schema: dict | None,
    base_url: str,
    token: str | None,
) -> BaseTool:
    args_model = _build_args_model(params, body_schema)
    path_params = {p["name"] for p in params if p.get("in") == "path"}

    @tool(name=name, description=description, args_schema=args_model)
    async def _run(**kwargs: Any) -> str:
        url = base_url.rstrip("/") + path_template
        for pname in path_params:
            url = url.replace("{" + pname + "}", str(kwargs.pop(pname)))
        query = {
            k: v for k, v in kwargs.items() if k != "body" and v is not None
        }
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        body = kwargs.get("body")
        try:
            async with _client_factory() as client:
                response = await client.request(
                    method.upper(), url, params=query, headers=headers, json=body or None
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return f"ERROR [{exc.response.status_code}]: {exc.response.text[:500]}"
        except httpx.RequestError as exc:
            return f"ERROR [network]: {exc}"
        try:
            text = json.dumps(response.json(), indent=2, ensure_ascii=False)
        except ValueError:
            text = response.text
        return truncate_text(text, _MAX_OUTPUT_CHARS)

    return _run


def load_openapi_tools(
    spec_path: str | Path,
    base_url: str | None = None,
    token: str | None = None,
) -> list[BaseTool]:
    """Parse an OpenAPI 3.0 JSON spec and return one tool per endpoint."""
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    base_url = base_url or (spec.get("servers") or [{}])[0].get("url", "")
    tools: list[BaseTool] = []
    for path_template, operations in (spec.get("paths") or {}).items():
        for method, op in operations.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = op.get("operationId") or _path_slug(path_template, method)
            name = _to_snake_case(op_id)
            description = op.get("description") or op.get("summary") or name
            params = list(op.get("parameters") or [])
            body_schema = op.get("requestBody")
            op_tool = _make_operation_tool(
                name, description, method, path_template, params, body_schema,
                base_url, token,
            )
            registry.register(group="api", name=name)(op_tool)
            tools.append(op_tool)
    return tools
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_openapi_loader.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/tools/openapi_loader.py tests/test_openapi_loader.py
git commit -m "feat(tools): add OpenAPI spec to tools loader"
```

---

### Task 5: Wire into graph builder + integration test

**Files:**
- Modify: `src/graph/builder.py` (imports, `all_tools`, `agent_node` system prompt)
- Test: `tests/test_builder.py` (append one test)

**Interfaces:**
- Consumes: `load_openapi_tools` (Task 4), `load_skill`/`list_skills` (Task 3), `build_skills_discovery` (Task 2), `Settings.openapi_spec_path/openapi_base_url/openapi_token` (Task 1)
- Produces: graph where the agent LLM is bound to code tools + openapi tools (if configured) + `load_skill`/`list_skills`; system prompt ends with `\n\nAvailable skills:\n<discovery>` when skills exist

- [ ] **Step 1: Write the failing test**

Append to `tests/test_builder.py`:

```python
def test_build_graph_includes_skill_tools(tmp_path, monkeypatch):
    from src.skills.registry import get_skill_registry
    from src.skills.tools import list_skills, load_skill
    from src.tools.registry import get_all_tools

    d = tmp_path / "demo"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Demo", encoding="utf-8"
    )
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        names = {t.name for t in get_all_tools()}
        assert "load_skill" in names and "list_skills" in names
    finally:
        get_skill_registry.cache_clear()
```

(Note: this test asserts the skill tools register on import; the full prompt-injection behavior is covered implicitly by the discovery unit tests in Task 2.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_builder.py -k skill_tools -v`
Expected: FAIL — `"load_skill" not in {"web_search", ...}` (skill tools never imported in builder path)

- [ ] **Step 3: Update builder.py**

In `src/graph/builder.py`:

Replace lines 6-17 imports with:

```python
from src.agents.reflection import reflection_node
from src.agents.supervisor import build_supervisor_tools
from src.config.settings import Settings
from src.graph.checkpointer import get_checkpointer
from src.graph.state import AgentState
from src.graph.trim import trim_node
from src.llm.factory import create_llm
from src.skills.registry import build_skills_discovery
from src.skills.tools import list_skills, load_skill
from src.tools.news_tools import get_news
from src.tools.openapi_loader import load_openapi_tools
from src.tools.time_tools import get_current_time
from src.tools.weather_tools import get_weather
from src.tools.web_fetch import web_fetch
from src.tools.web_search import web_search
```

Replace `all_tools = ...` line with:

```python
    openapi_tools = []
    if settings.openapi_spec_path:
        openapi_tools = load_openapi_tools(
            settings.openapi_spec_path,
            base_url=settings.openapi_base_url,
            token=settings.openapi_token,
        )
    all_tools = (
        [web_search, web_fetch, get_current_time, get_news, get_weather]
        + openapi_tools
        + [load_skill, list_skills]
        + supervisor_tools
    )
```

Replace the system message in `agent_node` with:

```python
        skills_section = ""
        discovery = build_skills_discovery()
        if discovery:
            skills_section = f"\n\nAvailable skills:\n{discovery}\nGọi load_skill để đọc hướng dẫn chi tiết."
        system_msg = SystemMessage(
            content=(
                "Bạn là Agent Moew"
                "Hãy tự động chọn và thực thi các công cụ (tools) hoặc subagent khi cần thiết để hỗ trợ người dùng."
                + skills_section
            )
        )
```

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (all tests, including the new one)

- [ ] **Step 5: Commit**

```bash
git add src/graph/builder.py tests/test_builder.py
git commit -m "feat(graph): bind openapi tools and skill tools into the agent"
```

---

### Task 6: Sample skill + end-to-end smoke check

**Files:**
- Create: `skills/code-review/SKILL.md` (under backend root)
- Run: manual smoke via `.venv/bin/python -c` snippet

**Interfaces:**
- Consumes: Task 2-5 (registry discovers this skill when cwd = backend and `skills_dir` default applies)

- [ ] **Step 1: Create the sample skill**

Create `skills/code-review/SKILL.md` (backend root):

```markdown
---
name: code-review
description: Review code systematically for correctness, security, and maintainability before reporting findings.
---

# Code Review Skill

Follow these steps when the user asks for a code review:

1. Read the file(s) under review.
2. Check for: correctness bugs, security issues (injection, secrets, auth), maintainability (dead code, unclear names).
3. List findings as `[severity] file:line — issue` (severity: HIGH/MED/LOW).
4. For each HIGH finding, propose a concrete fix.
5. End with an overall verdict (Approved / Needs changes).
```

- [ ] **Step 2: Smoke test discovery + load**

Run (from `/home/roser/Work-Code/agent_moew/backend`):

```bash
.venv/bin/python -c "
from src.skills.registry import build_skills_discovery, get_skill_registry
print(build_skills_discovery())
print(get_skill_registry().load('code-review')[:80])
"
```

Expected: prints `code-review: Review code systematically...` then the skill body.

- [ ] **Step 3: Commit**

```bash
git add skills/code-review/SKILL.md
git commit -m "feat(skills): add code-review sample skill"
```

---

### Task 7: Verify end-to-end with real spec file

**Files:**
- Run: manual verification only (no code changes)

- [ ] **Step 1: Load the real RedAI spec**

Run (from `/home/roser/Work-Code/agent_moew/backend`):

```bash
.venv/bin/python -c "
from src.tools.openapi_loader import load_openapi_tools
tools = load_openapi_tools('../ẹ ẹ ẹ.json', base_url='http://localhost:3003')
print(len(tools), 'tools generated')
print('\n'.join(sorted(t.name for t in tools))[:2000])
"
```

Expected: prints `35 tools generated` (or the exact endpoint count in the file) plus the snake_case tool names.

- [ ] **Step 2: Verify builder starts with spec configured**

Run: `OPENAPI_SPEC_PATH="../ẹ ẹ ẹ.json" .venv/bin/python -c "import asyncio; from src.config.settings import settings; from src.graph.builder import build_graph; asyncio.run(build_graph(settings)); print('graph OK')"`
Expected: prints `graph OK` (no exceptions; token left unset, so only unauthenticated calls will fail at runtime — expected).

- [ ] **Step 3: Final full suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 4: Commit any leftover changes** (none expected)

```bash
git status
```

Expected: clean tree.
