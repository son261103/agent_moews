# Design: Skills + OpenAPI File-Based Tools

Date: 2026-08-13
Status: Approved by user

## Problem

Agent Moew currently only supports code-defined tools (`@tool` + ToolRegistry).
Two gaps:

1. **No skills** — the agent cannot load markdown workflow instructions on demand
   (e.g. a TDD skill, a debugging skill). Every capability must be executable code.
2. **No file-based tools** — integrating an external REST API (e.g. RedAI, OpenAPI
   3.0 spec with 35 endpoints, JWT auth) requires hand-writing one Python `@tool`
   per endpoint. 100 endpoints = 100 functions to write and maintain.

## Goal

- Skills: agent can discover and load `SKILL.md` instruction files at runtime via
  tools, then follow the workflow they describe (progressive disclosure:
  discovery → read → execute).
- File-based tools: one small self-written converter reads an OpenAPI spec file
  and generates one `@tool` per endpoint automatically. No third-party packages,
  no MCP servers, no per-endpoint hand-written code.
- Keep existing graph scaffolding (trim_history / reflect / save_memory /
  checkpointer / supervisor) intact. No new graph nodes or edges.

## Architecture

```
                     ┌────────────────────────────┐
                     │   agent_node (LLM)         │
                     │  system prompt chứa:       │
                     │  - skills discovery        │
                     │    (name + description)    │
                     │  bind_tools:               │
                     │  - tool code (registry)    │
                     │  - tool từ file (OpenAPI)  │
                     │  - load_skill, list_skills │
                     └──────────────┬─────────────┘
                                    │ tool_calls
                                    ▼
                             ┌─────────────┐
                             │ ToolNode    │
                             └──┬──────┬───┘
                ┌───────────────┘      └───────────────┐
                ▼                                      ▼
     ┌────────────────────┐                ┌────────────────────┐
     │ load_skill(name)   │                │ <endpoint>_tool    │
     │ → đọc SKILL.md     │                │ (sinh từ OpenAPI)  │
     │ → trả nội dung về  │                │ → httpx call API   │
     │   context          │                │ → JWT từ env       │
     └────────────────────┘                └────────────────────┘
```

## Components

### 1. `src/tools/openapi_loader.py` (new) — converter tự code

- `load_openapi_tools(spec_path: str, base_url: str | None = None, token: str | None = None) -> list[BaseTool]`
  - Parse OpenAPI 3.0 JSON (`openapi` key, `paths`, `components`).
  - Iterate `paths[path][method]` for GET/POST/PUT/PATCH/DELETE; skip non-API
    keys (`parameters` at path level, `servers`, `summary`, `description`).
  - One `@tool` per operation:
    - Name: snake_case of `operationId` (e.g. `UserTemplateEmail_findAll` →
      `user_template_email_find_all`); fallback: `<method>_<path-slug>`.
    - Description: từ `description`/`summary` của operation.
    - Args: Pydantic model từ `parameters` (path + query + header) và
      `requestBody` (nếu có, JSON body). Query params không required → default.
    - Execution: build URL = `base_url` (env override) + path (điền path params),
      append query params, set `Authorization: Bearer <token>` (nếu có), gửi qua
      `httpx.AsyncClient`, timeout mặc định 30s.
    - Return: `response.json()` dạng JSON string (hoặc text nếu không phải JSON),
      cắt ngắn ~8K chars với ghi chú nếu bị cắt.
    - Error: trả về string lỗi có cấu trúc `ERROR [<status>]: <reason>` để LLM tự
      xử lý (không raise — tool phải trả string).
- Allowlist đơn giản: chỉ gọi tới host của `base_url` (từ env hoặc server đầu
  tiên trong spec), chặn URL lạ do LLM tự bịa.

### 2. `src/skills/registry.py` (new) — SkillRegistry

- `SkillRegistry(root: Path)` — scan `skills/*/SKILL.md`:
  - Parse YAML frontmatter (bắt buộc: `name`, `description`; bỏ qua file thiếu).
  - `list_skills() -> list[SkillInfo]` (name + description)
  - `load(name) -> str` — nội dung markdown (bỏ frontmatter); lỗi rõ nếu không tồn tại.
- Tools (đăng ký qua ToolRegistry, group `"skills"`):
  - `load_skill(name: str) -> str` — trả nội dung SKILL.md vào context.
  - `list_skills() -> str` — danh sách name + description.
- `build_skills_discovery() -> str` — chuỗi `name: description` để chèn vào system prompt.

### 3. `src/graph/builder.py` (sửa nhẹ)

- `all_tools = registry tools + openapi tools (nếu spec cấu hình) + load_skill + list_skills`
- `agent_node`: system prompt thêm section "Available skills:" từ
  `build_skills_discovery()`.
- Không đổi node/edge nào khác.

### 4. `src/config/settings.py` (sửa nhẹ)

- `openapi_spec_path: str | None = None` (đường dẫn file spec)
- `openapi_base_url: str | None = None` (override server, vd test server)
- `openapi_token: str | None = None` (JWT — secret, không log, không đưa cho LLM)
- `skills_dir: str = "skills"`

### 5. Thư mục `backend/skills/` (new) — skill library

- 1 skill mẫu để chứng minh luồng hoạt động (ví dụ `code-review` hoặc
  `test-driven-development` với SKILL.md mô tả các bước).
- Thêm skill mới = thêm thư mục + SKILL.md, không đụng code.

## Testing

- Unit test `openapi_loader`: parse spec mẫu (2-3 endpoints) → đúng số tool, tên,
  schema args; gọi tool với `httpx` mock → URL/headers/body đúng; lỗi HTTP → string lỗi.
- Unit test `skill registry`: frontmatter hợp lệ/thiếu field; `load` trả đúng nội dung;
  `list_skills`/`build_skills_discovery` đúng format.
- Integration: build graph → hỏi "dùng skill X làm việc Y" → assert tool `load_skill`
  được gọi và kết quả agent tiếp tục đúng.

## Out of scope (làm sau nếu cần)

- Retry/backoff tự động, idempotency key cho write endpoints.
- SSRF hardening ngoài host allowlist (DNS pinning, block private ranges).
- Dynamic tool registration khi load skill.
- MCP migration.
- Secret redaction trong output tool.
