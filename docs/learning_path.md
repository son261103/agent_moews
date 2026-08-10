# Agent Moew Learning Path

Follow these phases in order. Each phase builds on the previous one.

## Phase 1: Core Setup (Task 1)

- Understand Pydantic Settings for config management
- LLM factory pattern: single point to change models
- `.env` vs `.env.example`: never commit secrets

## Phase 2: Tools (Task 2)

- `@tool` decorator: how LangChain tools work
- Tool is just a function — LLM decides when to call it
- Sandboxing patterns: timeout, output capture, safe file ops

## Phase 3: Sub-agents & Reflection (Task 3)

- Sub-agent config: name, description, system_prompt, tools
- DeepAgent auto-invokes sub-agents based on task
- Reflection pattern: evaluate → maybe rewrite (max 3 rounds)

## Phase 4: Graph Orchestration (Task 4)

- AgentState schema: messages + custom fields
- Checkpointer: SQLite for thread persistence
- Graph wiring: entry point → nodes → conditional edges → END

## Phase 5: API (Task 5)

- FastAPI + SSE: streaming events from LangGraph to client
- Pydantic schemas for request/response
- CORS for Next.js frontend

## Phase 6: Observability (Task 6)

- LangSmith tracing: automatic with `langchain-core`
- Project organization in LangSmith dashboard
- `eval.py` script for quality evaluation (run manually, not in CI)

## Phase 7: Frontend (Task 7)

- Next.js App Router with TypeScript
- SSE client: reading streams from Python backend
- Agent steps panel: showing tool calls in real-time
- SWR for data fetching (threads list)

## Phase 8: Run It All

```bash
# Terminal 1
cd backend && source .venv/bin/activate && uvicorn src.api.main:create_app --factory --reload

# Terminal 2
cd frontend && npm run dev
```

Open http://localhost:3000, ask the agent a question, check LangSmith dashboard for traces.
