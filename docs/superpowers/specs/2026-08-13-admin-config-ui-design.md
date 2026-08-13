# Admin Config UI — Design Spec

**Date:** 2026-08-13
**Status:** Approved (user: "ok tiếp tục đi ạ")

## Goal

Give the user a frontend admin page to manage agent capabilities without touching code or `.env`:
- Import an OpenAPI spec file + fill in base URL and token → agent's API tools update **without restarting the backend**
- Create/edit/delete skills (SKILL.md) through a form → agent sees them immediately

## Decisions (user-approved)

1. **Trang admin riêng** in the Next.js frontend (`/admin`).
2. **Lưu DB + reload**: config stored in sqlite (`agent_moew.db`), a `POST /admin/reload` rebuilds the graph and swaps it in — no manual restart.
3. **Skill lưu DB luôn**: skills live in the DB; the filesystem registry is retired.
4. **DB-only**: `backend/skills/` directory is retired. The existing `code-review` skill is seeded into the DB on first run.

## Architecture

### 1. DB layer (backend/src/api/admin_store.py)

Same pattern as `ChatStore` (aiosqlite, `agent_moew.db` via `settings.db_path`).

Tables:

```sql
CREATE TABLE IF NOT EXISTS skills (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS openapi_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    spec_content TEXT NOT NULL DEFAULT '',
    base_url TEXT NOT NULL DEFAULT '',
    token TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`AdminStore` methods (all async):
- `connect()` / `close()`
- `seed_default_skill()` — if `skills` table empty, insert the `code-review` skill (content taken from the current `backend/skills/code-review/SKILL.md` body, which is then deleted from disk)
- `list_skills() -> list[SkillInfo]` (sorted by name)
- `get_skill(name) -> SkillInfo | None`
- `create_skill(name, description, content)` — raises `ValueError` on duplicate name
- `update_skill(name, description, content)` — raises `KeyError` if missing
- `delete_skill(name)` — raises `KeyError` if missing
- `get_openapi_config() -> OpenApiConfig` (dataclass: spec_content, base_url, token, enabled)
- `save_openapi_config(spec_content, base_url, token, enabled)`

### 2. SkillRegistry becomes DB-backed (backend/src/skills/registry.py)

Public API unchanged — `SkillInfo` dataclass, `list_skills()`, `load(name)`, `build_skills_discovery()`, `get_skill_registry()` — so `src/skills/tools.py` and `src/graph/builder.py` need **no changes**.

Internals change:
- `SkillRegistry` holds an `AdminStore` (or a store-provider callable) instead of a filesystem root.
- `list_skills()` queries the DB **per call** (no caching of results) → UI saves are visible to the agent immediately.
- `load(name)` queries the DB, raises `KeyError(f"Skill not found: {name}")` as before.
- `build_skills_discovery()` unchanged (uses `list_skills()`).
- `get_skill_registry()` stays `@lru_cache`d (the *instance* is cached; queries are per-call).
- The registry needs the store before the app lifespan connects it. Solution: registry holds a **store provider** (`Callable[[], AdminStore]`) that resolves lazily; `main.py` lifespan sets the provider to the connected store. Default provider returns a store that opens its own connection on demand (used by tests and standalone scripts).

### 3. Admin API (backend/src/api/routes/admin.py)

Router under `/api/v1/admin`, registered in `main.py`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/admin/config` | `{openapi: {enabled, base_url, token_masked, spec_title, endpoint_count}, skills: [{name, description}]}` — token masked (`sk-****last4` style, or `****` if empty) |
| PUT | `/api/v1/admin/openapi` | Body: `{spec_content: str, base_url: str, token: str, enabled: bool}`. Validates spec (parses JSON, counts operations via the same logic as `load_openapi_tools`), saves to DB. Returns updated config summary. |
| POST | `/api/v1/admin/skills` | Body: `{name, description, content}`. Validates name (lowercase-hyphenated, matches `^[a-z0-9-]+$`), validates frontmatter (name+description present), saves. 409 on duplicate. |
| PUT | `/api/v1/admin/skills/{name}` | Body: `{description, content}`. 404 if missing. |
| DELETE | `/api/v1/admin/skills/{name}` | 404 if missing. |
| POST | `/api/v1/admin/reload` | Reads openapi config from DB → materializes spec to `backend/specs/imported.json` → sets `app.state.settings.openapi_spec_path/base_url/token` → `build_graph(settings)` → swaps `app.state.graph`. Returns `{ok: true, endpoint_count, skills_count}`. |

Validation helpers (in `admin.py` or `admin_store.py`):
- `validate_skill_name(name)` — regex `^[a-z0-9-]+$`, ≤64 chars
- `parse_skill_frontmatter(content)` — reuse `_parse_frontmatter` from registry (export it), require `name` + `description`
- `count_operations(spec_dict)` — paths × methods GET/POST/PUT/PATCH/DELETE (same filter as loader)

### 4. Reload flow (main.py lifespan + reload endpoint)

- `lifespan`: after `build_graph`, create `AdminStore`, connect, `seed_default_skill()`, set the registry's store provider.
- `POST /admin/reload`: as above. In-flight SSE chat sessions keep running on the old graph object (accepted limitation). The old graph's checkpointer connection is closed after swap (same pattern as lifespan shutdown).

### 5. Frontend (frontend/app/admin/page.tsx + lib/api.ts)

- New page `app/admin/page.tsx` ("use client"), same Tailwind style as chat page. Header link "Admin" added to `app/page.tsx` (small button in the sidebar or top bar) and a "← Chat" link back.
- Section **OpenAPI**:
  - File input (accept `.json`) → reads file, fills a textarea (editable) with the spec content
  - Fields: Base URL, Token (password input), Enabled toggle
  - "Lưu & Reload" button → `PUT /admin/openapi` then `POST /admin/reload`, shows result (endpoint count, skills count)
  - Status card: current enabled/base_url/token_masked/spec_title/endpoint_count (from `GET /admin/config`)
- Section **Skills**:
  - List of skills (name + description) with Edit / Delete buttons
  - Create/Edit form: name (create only), description, content textarea with a frontmatter template prefilled
  - Delete asks for confirmation (window.confirm)
- `lib/api.ts`: add `getAdminConfig()`, `saveOpenApiConfig()`, `reloadGraph()`, `createSkill()`, `updateSkill()`, `deleteSkill()` — same fetch pattern as existing functions.

## Error handling

- All admin endpoints return structured errors: `{"detail": "..."}` with proper status codes (400 validation, 404 missing, 409 duplicate).
- Spec validation failure → 400 with reason (invalid JSON / no operations found).
- Frontend shows `detail` message inline (simple alert/error text).

## Testing

- **Backend** (pytest, asyncio_mode=auto, run from `backend/` via `.venv/bin/python -m pytest`):
  - `tests/test_admin_store.py` — CRUD + seed + openapi config save/load (tmp DB path)
  - `tests/test_admin_routes.py` — httpx AsyncClient against `create_app` with a tmp settings (tmp db_path): config GET, openapi PUT (valid + invalid spec), skills POST/PUT/DELETE (incl. 409/404), reload (asserts graph swapped + settings updated)
  - `tests/test_skills_registry.py` — **rewrite** existing 5 tests to DB-backed registry (tmp DB, seeded store)
  - `tests/test_skills_tools.py` — keep, adapt store wiring if needed
  - `tests/test_builder.py` — keep (builder unchanged)
- **Frontend**: no test infra exists — manual smoke: run backend + `npm run dev`, exercise admin page flows (import spec, save+reload, create/edit/delete skill, verify agent sees new skill in chat).

## Out of scope

- Auth on the admin page (localhost-only app)
- Token encryption (plaintext in local DB)
- Hot-reload of in-flight chat sessions (old graph finishes; new sessions use new graph)
- Multi-user / multi-config
- File-based skills directory (retired)

## Files touched

- Create: `backend/src/api/admin_store.py`, `backend/src/api/routes/admin.py`, `backend/tests/test_admin_store.py`, `backend/tests/test_admin_routes.py`, `frontend/app/admin/page.tsx`
- Modify: `backend/src/skills/registry.py` (DB-backed), `backend/src/api/main.py` (router + lifespan wiring), `backend/tests/test_skills_registry.py` (rewrite), `backend/tests/test_skills_tools.py` (adapt), `frontend/lib/api.ts` (admin functions), `frontend/app/page.tsx` (Admin link)
- Delete: `backend/skills/code-review/SKILL.md` (seeded into DB instead)