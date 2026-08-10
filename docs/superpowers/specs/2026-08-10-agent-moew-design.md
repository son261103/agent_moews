# Agent Moew — Design Document

**Date:** 2026-08-10
**Status:** Approved

## Goal

Build a single, production-grade AI agent project (`agent-moew`) with full capabilities:
planning, tool use, sub-agents, memory, self-reflection, and observability.
The project serves dual purpose: a working agent for real tasks and a structured
learning path for LangChain, LangGraph, DeepAgents, and LangSmith.

**Out of scope (phase 2):** RAG over private documents, deployment (Docker, hosting), authentication.

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| LLM Foundation | LangChain | Model abstraction, tools, prompts, output parsers |
| Orchestration | LangGraph | Stateful graph workflows, checkpointing, memory |
| Agent Pattern | DeepAgents (`deepagents`) | Planning, sub-agents, virtual filesystem |
| Observability | LangSmith | Tracing, evaluation, debugging |
| LLM Provider | OpenAI | gpt-4o / o1, configurable via settings |
| Search | Tavily | Web search API (AI-optimized results) |
| Backend | FastAPI (Python) | HTTP API + SSE streaming |
| Frontend | Next.js 15 (TypeScript) | Chat UI, agent steps visualization |
| Persistence | SQLite | Checkpointer (threads) + Store (long-term memory) |

## Architecture

```
Next.js UI (port 3000)
    | SSE streaming (POST /chat/stream)
FastAPI (port 8000)
    | astream_events()
Agent Core (LangGraph)
    |-- DeepAgent (planning, sub-agents, virtual fs)
    |-- Reflection node (self-evaluation)
    |-- Memory nodes (checkpointer + store)
Tools layer (LangChain)
    |-- Tavily search / web fetch
    |-- Python REPL (sandboxed)
    |-- File read/write
LangSmith (tracing everything)
```

## Project Structure

```
agent-moew/
├── backend/
│   ├── src/
│   │   ├── config/settings.py       # Pydantic Settings, reads .env
│   │   ├── llm/factory.py           # LLM factory, model routing
│   │   ├── tools/
│   │   │   ├── web_search.py        # Tavily search tool
│   │   │   ├── web_fetch.py         # Fetch URL content → markdown
│   │   │   ├── python_repl.py       # Sandboxed Python execution
│   │   │   └── file_tools.py        # Workspace file read/write
│   │   ├── agents/
│   │   │   ├── main_agent.py        # DeepAgent (create_deep_agent)
│   │   │   ├── sub_agents.py        # Specialized sub-agents
│   │   │   └── reflection.py        # Self-evaluation node
│   │   ├── graph/
│   │   │   ├── builder.py           # LangGraph graph wiring
│   │   │   ├── state.py             # State schema
│   │   │   └── checkpointer.py      # SQLite checkpointer
│   │   ├── memory/store.py          # Long-term memory (SQLite store)
│   │   ├── observability/
│   │   │   ├── langsmith.py         # Tracer setup
│   │   │   └── eval.py              # LangSmith evaluation script
│   │   └── api/
│   │       ├── main.py              # FastAPI app, CORS
│   │       ├── routes/
│   │       │   ├── chat.py          # POST /chat/stream (SSE)
│   │       │   └── threads.py       # Thread CRUD
│   │       └── schemas.py           # Request/response models
│   ├── tests/                       # pytest suite
│   ├── .env.example                 # OPENAI_API_KEY, TAVILY_API_KEY, LANGSMITH_*
│   └── pyproject.toml
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # Main chat page
│   │   └── threads/[id]/page.tsx    # Thread history view
│   ├── components/
│   │   ├── ChatWindow.tsx           # Message list + streaming
│   │   ├── MessageBubble.tsx        # Single message
│   │   ├── AgentSteps.tsx           # Agent activity panel (plan, tool calls)
│   │   └── ThreadSidebar.tsx        # Thread list
│   ├── lib/
│   │   ├── sse.ts                   # SSE client
│   │   └── api.ts                   # API calls
│   ├── .env.local.example           # NEXT_PUBLIC_API_URL
│   └── package.json
├── data/                            # SQLite file (gitignored, auto-created)
├── docs/
│   └── learning_path.md             # Module-by-module curriculum
└── AGENTS.md                        # Project conventions
```

### Sub-agents

Sub-agents are **defined upfront** (name, description, system_prompt, tools) but **DeepAgent decides when to invoke which one** — no manual calling code needed.

Each sub-agent can spawn its own sub-agents recursively if configured.

```python
# sub_agents.py — configuration only
sub_agents = [
    {"name": "researcher", "description": "Internet research specialist", "tools": [web_search, web_fetch]},
    {"name": "coder", "description": "Python developer", "tools": [python_repl, read_file, write_file]},
]
```

## Data Flow

1. User sends message from Next.js → FastAPI `POST /chat/stream` with `thread_id`
2. FastAPI loads thread from SQLite checkpointer, calls `graph.astream_events()`
3. DeepAgent node: plans (write_todos), executes tools, spawns sub-agents as needed
4. Reflection node: evaluates output quality, sends back for rewrite if poor (max 3 rounds)
5. Memory node: saves durable user facts to SQLite store
6. Events stream back to frontend via SSE:
   - `plan` — todo list created
   - `tool_start` / `tool_end` — tool execution with truncated results
   - `token` — streaming text chunks
   - `reflection` — score and feedback
   - `done` — final state

## Error Handling

| Scenario | Strategy |
|---|---|
| Tool failure (timeout, crash) | Retry 2x with exponential backoff (tenacity). On final failure, return error to agent for self-recovery |
| LLM rate limit / timeout | Retry 3x backoff. On timeout, fallback to smaller model (gpt-4o → gpt-4o-mini) |
| SSE disconnect mid-stream | Client reconnects with `last_event_id`, resumes from checkpoint |
| Context window overflow | Count tokens before LLM call. If over limit, summarize early conversation, keep recent messages intact |
| Reflection infinite loop | Max 3 rounds. If still poor, return current output with warning flag |
| Python REPL safety | 30s timeout, block `os.system`/`subprocess`, restrict file access to `workspace/` |

## Testing

- **Unit tests** (`test_tools.py`): Mock HTTP responses (httpx_mock for Tavily), no real API calls
- **Agent tests** (`test_agents.py`): Use `FakeListLLM` / `GenericFakeChatModel` to test planning, sub-agent spawning
- **Reflection tests** (`test_reflection.py`): Verify poor input triggers rewrite signal
- **Integration tests** (`test_graph.py`): Full graph flow with fake LLM, checkpoint resume verification
- **API tests** (`test_api.py`): FastAPI TestClient, SSE stream format validation
- **E2E (optional)**: 1 test calling real OpenAI, marked `@pytest.mark.slow`, skipped in CI
- **LangSmith eval** (`eval.py`): Separate script, not in test suite — creates datasets, runs LLM-as-judge evaluation

## Development Workflow

Two terminals:

```bash
# Terminal 1 — backend
cd backend && uvicorn src.api.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

Environment setup:

```bash
# backend/.env (copy from .env.example, fill keys)
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=agent-moew
```

## Learning Path

Each module maps to a phase in `docs/learning_path.md`:

1. **Core setup** — settings, LLM factory, first LangChain chain
2. **Tools** — build each tool independently, test with mock
3. **LangGraph** — state schema, graph building, checkpointing
4. **DeepAgents** — DeepAgent pattern, sub-agents, virtual filesystem
5. **Memory** — long-term store, user preferences across sessions
6. **Reflection** — self-evaluation loop, quality improvement
7. **FastAPI** — SSE streaming, thread management
8. **Next.js** — chat UI, agent steps panel, thread sidebar
9. **Observability** — LangSmith tracing, evaluation, datasets

## Phase 2 (Future)

- RAG module: add `retrieval_tool` as a new tool file, no architecture change
- Deployment: Dockerfiles per side, Postgres instead of SQLite, Vercel + Railway
- Authentication: API keys, rate limiting
