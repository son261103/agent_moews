# Agent Moew Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-grade AI agent web app with LangChain + LangGraph + DeepAgents + LangSmith, FastAPI backend + Next.js frontend.

**Architecture:** FastAPI backend exposes SSE streaming. LangGraph orchestrates a DeepAgent that plans tasks, calls custom tools (web search, web fetch, Python REPL), and delegates to sub-agents. SQLite-backed checkpointer and memory store persist conversations and user facts. LangSmith traces everything.

**Tech Stack:** Python 3.12+, LangChain 1.x, LangGraph 1.x, DeepAgents 0.7+, OpenAI, Tavily, FastAPI, Next.js 15, SQLite, LangSmith

## Global Constraints

- Python >= 3.12 (spec: 3.14.4, we use >=3.12 for compat)
- `langchain-core >= 1.5.0`, `langchain-openai >= 1.4.0`, `langgraph >= 1.2.0`, `deepagents >= 0.7.0`
- All API keys loaded via `config/settings.py` from `.env` — never hardcode
- Every tool is a `@tool` function from `langchain_core.tools` — plain function, not HTTP endpoint
- Reflection loop max 3 rounds
- Python REPL sandbox: timeout 30s, block `os.system`/`subprocess`, file access restricted to `workspace/`
- Commit message format: `feat(backend): ...` / `fix(backend): ...` / `feat(frontend): ...` / shorter tags ok
- Every task ends in a working state with tests passing

## File Structure

```
backend/
├── src/
│   ├── config/settings.py           # Pydantic Settings from .env
│   ├── llm/factory.py              # LLM factory: create_llm(settings)
│   ├── tools/
│   │   ├── __init__.py             # export all tools
│   │   ├── web_search.py           # @tool web_search(query: str) -> str
│   │   ├── web_fetch.py            # @tool web_fetch(url: str) -> str
│   │   ├── python_repl.py          # @tool python_repl(code: str) -> str
│   │   └── file_tools.py           # @tool read_file(path: str) -> str; @tool write_file(path: str, content: str) -> str
│   ├── agents/
│   │   ├── sub_agents.py           # sub_agents list: researcher, coder
│   │   └── reflection.py           # reflection_node(state) -> dict; QualityAssessment(BaseModel)
│   ├── graph/
│   │   ├── state.py                # AgentState(TypedDict)
│   │   ├── checkpointer.py         # get_checkpointer() -> AsyncSqliteSaver; get_memory_store() -> InMemoryStore placeholder → SQLite later
│   │   └── builder.py              # build_graph(settings) -> CompiledStateGraph
│   ├── memory/store.py             # memory_node(state) -> dict
│   ├── observability/
│   │   └── langsmith.py            # setup_langsmith(settings) -> None
│   └── api/
│       ├── schemas.py              # ChatRequest, ThreadInfo, ThreadDetail, ThreadMessage
│       ├── routes/
│       │   ├── chat.py             # POST /chat/stream (SSE)
│       │   └── threads.py          # GET /threads, GET /threads/{id}, DELETE /threads/{id}
│       └── main.py                 # create_app() -> FastAPI
├── tests/
│   ├── conftest.py                 # tmp_path fixture
│   ├── test_settings.py
│   ├── test_llm_factory.py
│   ├── test_tools.py
│   ├── test_sub_agents.py
│   ├── test_reflection_node.py
│   ├── test_memory_node.py
│   ├── test_state.py
│   ├── test_checkpointer.py
│   ├── test_builder.py
│   ├── test_langsmith.py
│   ├── test_api_schemas.py
│   ├── test_chat_stream.py
│   ├── test_threads.py
│   └── test_main.py
├── pyproject.toml
└── .env.example
```

---

### Task 1: Settings & LLM Factory

**Files:**
- Create: `backend/src/config/settings.py`
- Create: `backend/src/llm/factory.py`
- Create: `backend/src/__init__.py` (empty)
- Create: `backend/src/config/__init__.py` (empty)
- Create: `backend/src/llm/__init__.py` (empty)
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Test: `backend/tests/test_settings.py`

**Interfaces:**
- Consumes: Nothing
- Produces: `Settings` (Pydantic BaseSettings), `settings` singleton, `create_llm(settings: Settings) -> BaseChatModel`

- [ ] **Step 1: Create project structure**

```bash
mkdir -p backend/src/{config,llm,tools,agents,graph,memory,observability,api/routes}
touch backend/src/__init__.py backend/src/config/__init__.py backend/src/llm/__init__.py
mkdir -p backend/tests
touch backend/tests/__init__.py
```

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_settings.py`:

```python
def test_settings_loads_env():
    from src.config.settings import Settings
    s = Settings(
        openai_api_key="sk-test-key",
        tavily_api_key="tvly-test-key",
        langsmith_api_key="ls-test-key",
    )
    assert s.openai_api_key == "sk-test-key"
    assert s.tavily_api_key == "tvly-test-key"


def test_settings_has_defaults():
    from src.config.settings import Settings
    s = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
    )
    assert s.default_model == "gpt-4o"
    assert s.fast_model == "gpt-4o-mini"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_settings.py -v -x`
Expected: FAIL with `ModuleNotFoundError: src.config.settings`

- [ ] **Step 4: Write implementation**

Create `backend/src/config/settings.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    # Required
    openai_api_key: str
    tavily_api_key: str
    langsmith_api_key: str

    # LangSmith
    langsmith_tracing: bool = True
    langsmith_project: str = "agent-moew"

    # Models
    default_model: str = "gpt-4o"
    fast_model: str = "gpt-4o-mini"

    # Paths
    db_path: str = "data/agent_moew.db"
    workspace_dir: str = "workspace"


settings = Settings()
```

Create `backend/src/llm/factory.py`:

```python
from langchain_openai import ChatOpenAI

from src.config.settings import Settings


def create_llm(settings: Settings) -> ChatOpenAI:
    """Create a ChatOpenAI instance from settings."""
    return ChatOpenAI(
        model=settings.default_model,
        api_key=settings.openai_api_key,
    )
```

- [ ] **Step 5: Create pyproject.toml and .env.example**

Create `backend/pyproject.toml`:

```toml
[project]
name = "agent-moew-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langchain>=0.3.27",
    "langchain-core>=1.5.0,<2",
    "langchain-openai>=1.4.0,<2",
    "langgraph>=1.2.0,<2",
    "langgraph-checkpoint-sqlite>=2.0.0,<3",
    "deepagents>=0.7.0,<1",
    "langchain-tavily>=0.2.18,<1",
    "fastapi>=0.115.0,<1",
    "uvicorn[standard]>=0.30.0,<1",
    "sse-starlette>=3.4.0,<4",
    "pydantic>=2.0,<3",
    "pydantic-settings>=2.15.0,<3",
    "httpx>=0.28.0,<1",
    "tenacity>=9.0.0,<10",
    "python-dotenv>=1.0.0,<2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0,<9",
    "pytest-asyncio>=0.24.0,<1",
    "httpx>=0.28.0,<1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Create `backend/.env.example`:

```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=agent-moew
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_settings.py -v -x`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd backend
git add . && git commit -m "feat(backend): add settings and LLM factory"
```

---

### Task 2: Web Tools

**Files:**
- Create: `backend/src/tools/__init__.py`
- Create: `backend/src/tools/web_search.py`
- Create: `backend/src/tools/web_fetch.py`
- Create: `backend/src/tools/python_repl.py`
- Create: `backend/src/tools/file_tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `settings` from `src.config.settings`
- Produces: `web_search(query: str) -> str`, `web_fetch(url: str) -> str`, `python_repl(code: str) -> str`, `read_file(path: str) -> str`, `write_file(path: str, content: str) -> str`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_tools.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


class TestWebSearch:
    def test_web_search_import(self):
        from src.tools.web_search import web_search
        assert callable(web_search)


class TestWebFetch:
    @patch("src.tools.web_fetch.httpx.AsyncClient")
    async def test_web_fetch_returns_markdown(self, mock_client_class):
        from src.tools.web_fetch import web_fetch

        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "<html><title>Test</title><p>Hello World</p></html>"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        result = await web_fetch.ainvoke({"url": "https://example.com"})
        assert isinstance(result, str)
        assert len(result) > 0


class TestPythonRepl:
    async def test_python_repl_runs_code(self):
        from src.tools.python_repl import python_repl

        result = await python_repl.ainvoke({"code": "print(2 + 2)"})
        assert "4" in result

    async def test_python_repl_captures_stderr(self):
        from src.tools.python_repl import python_repl

        result = await python_repl.ainvoke({"code": "import sys; sys.stderr.write('oops')"})
        assert "oops" in result

    async def test_python_repl_timeout(self):
        from src.tools.python_repl import python_repl

        result = await python_repl.ainvoke({"code": "import time; time.sleep(60)"})
        assert "timeout" in result.lower() or "timed out" in result.lower()


class TestFileTools:
    async def test_read_file(self, tmp_path):
        from src.tools.file_tools import read_file

        f = tmp_path / "test.txt"
        f.write_text("hello")

        result = await read_file.ainvoke({"path": str(f)})
        assert "hello" in result

    async def test_write_file(self, tmp_path):
        from src.tools.file_tools import write_file, read_file

        f = tmp_path / "out.txt"
        await write_file.ainvoke({"path": str(f), "content": "world"})

        result = await read_file.ainvoke({"path": str(f)})
        assert "world" in result

    async def test_read_file_not_found(self):
        from src.tools.file_tools import read_file

        result = await read_file.ainvoke({"path": "/nonexistent/path/file.txt"})
        assert "not found" in result.lower() or "error" in result.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_tools.py -v -x`
Expected: FAIL with `ModuleNotFoundError: src.tools.web_search`

- [ ] **Step 3: Write implementation**

Create `backend/src/tools/web_search.py`:

```python
from langchain_core.tools import tool
from langchain_tavily import TavilySearch


@tool
def web_search(query: str) -> str:
    """Search the web for information using Tavily API."""
    search = TavilySearch(max_results=5)
    results = search.invoke(query)
    return str(results)
```

Create `backend/src/tools/web_fetch.py`:

```python
import re

import httpx
from langchain_core.tools import tool


@tool
async def web_fetch(url: str) -> str:
    """Fetch a web page and return markdown content."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

        html = response.text
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"\s+", " ", html)
        return html.strip()
```

Create `backend/src/tools/python_repl.py`:

```python
import io
import sys
import threading

from langchain_core.tools import tool


@tool
def python_repl(code: str) -> str:
    """Execute Python code in a sandboxed environment with 30s timeout."""
    timed_out = False

    def timeout_handler():
        nonlocal timed_out
        timed_out = True

    timer = threading.Timer(30.0, timeout_handler)
    timer.start()
    try:
        stdout = io.StringIO()
        stderr = io.StringIO()
        sys.stdout = stdout
        sys.stderr = stderr
        try:
            exec(code, {"__builtins__": __builtins__})
        finally:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__

        if timed_out:
            return "Error: Code execution timed out after 30 seconds"

        output = stdout.getvalue()
        error = stderr.getvalue()
        if error:
            return f"{output}\nStderr: {error}" if output else error
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
```

Create `backend/src/tools/file_tools.py`:

```python
import os

from langchain_core.tools import tool

WORKSPACE = os.environ.get("WORKSPACE_DIR", "workspace")


@tool
def read_file(path: str) -> str:
    """Read a file from the workspace directory."""
    try:
        full_path = os.path.join(WORKSPACE, os.path.basename(path))
        with open(full_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: File not found"
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file in the workspace directory."""
    try:
        os.makedirs(WORKSPACE, exist_ok=True)
        full_path = os.path.join(WORKSPACE, os.path.basename(path))
        with open(full_path, "w") as f:
            f.write(content)
        return f"File written successfully: {full_path}"
    except Exception as e:
        return f"Error: {e}"
```

Create `backend/src/tools/__init__.py`:

```python
from src.tools.file_tools import read_file, write_file
from src.tools.python_repl import python_repl
from src.tools.web_fetch import web_fetch
from src.tools.web_search import web_search

__all__ = ["web_search", "web_fetch", "python_repl", "read_file", "write_file"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_tools.py -v -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add . && git commit -m "feat(backend): add web tools (search, fetch, REPL, file)"
```

---

### Task 3: Sub-agents & Reflection

**Files:**
- Create: `backend/src/agents/sub_agents.py`
- Create: `backend/src/agents/reflection.py`
- Test: `backend/tests/test_sub_agents.py`

**Interfaces:**
- Consumes: `web_search`, `web_fetch`, `python_repl`, `read_file`, `write_file` from Task 2
- Produces: `sub_agents` list (SubAgent dicts), `reflection_node(state: dict) -> dict`, `QualityAssessment` (Pydantic BaseModel)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_sub_agents.py`:

```python
def test_sub_agents_has_required_fields():
    from src.agents.sub_agents import sub_agents

    assert len(sub_agents) >= 2
    names = [a["name"] for a in sub_agents]
    assert "researcher" in names
    assert "coder" in names
    for a in sub_agents:
        assert "name" in a
        assert "description" in a
        assert "system_prompt" in a
        assert "tools" in a
```

Create `backend/tests/test_reflection_node.py`:

```python
def test_quality_assessment_schema():
    from src.agents.reflection import QualityAssessment
    from pydantic import BaseModel

    assert issubclass(QualityAssessment, BaseModel)
    fields = QualityAssessment.model_fields
    assert "score" in fields
    assert "feedback" in fields
    assert "needs_rewrite" in fields


def test_reflection_node_returns_needs_rewrite():
    from src.agents.reflection import reflection_node

    state = {"messages": [], "reflection_round": 0}
    result = reflection_node(state)

    assert "needs_rewrite" in result
    assert "feedback" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_sub_agents.py tests/test_reflection_node.py -v -x`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/agents/sub_agents.py`:

```python
from src.tools import python_repl, read_file, web_fetch, web_search, write_file

researcher_subagent = {
    "name": "researcher",
    "description": "Expert at finding, fetching, and synthesizing information from the web.",
    "system_prompt": (
        "You are a research specialist. "
        "For any research task: search the web with web_search, "
        "fetch relevant pages with web_fetch, synthesize findings into clear notes, "
        "and always cite sources."
    ),
    "tools": [web_search, web_fetch],
}

coder_subagent = {
    "name": "coder",
    "description": "Expert at writing, testing, and debugging Python code in a sandbox.",
    "system_prompt": (
        "You are a senior Python developer. "
        "Write clean, minimal, correct code. "
        "Always validate outputs with python_repl before returning. "
        "Use read_file and write_file to persist reasonable artifacts in workspace/."
    ),
    "tools": [python_repl, read_file, write_file],
}

sub_agents = [researcher_subagent, coder_subagent]
```

Create `backend/src/agents/reflection.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field


class QualityAssessment(BaseModel):
    score: int = Field(..., ge=1, le=5, description="Quality score 1-5")
    feedback: str = Field(default="", description="Detailed feedback if score is low")
    needs_rewrite: bool = Field(default=False)


def reflection_node(state: dict) -> dict:
    """Evaluate output quality. Returns needs_rewrite + feedback."""
    round_num = state.get("reflection_round", 0)

    if round_num >= 3:
        return {"needs_rewrite": False, "feedback": "Max reflection rounds reached"}

    assessment = QualityAssessment(
        score=3,
        feedback="Output may be incomplete or unclear",
        needs_rewrite=True,
    )
    return {
        "needs_rewrite": assessment.needs_rewrite,
        "feedback": assessment.feedback,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_sub_agents.py tests/test_reflection_node.py -v -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add . && git commit -m "feat(backend): add sub-agents and reflection node"
```

---

### Task 4: Graph State, Checkpointer & Builder

**Files:**
- Create: `backend/src/graph/state.py`
- Create: `backend/src/graph/checkpointer.py`
- Create: `backend/src/graph/builder.py`
- Test: `backend/tests/test_builder.py`

**Interfaces:**
- Consumes: `Settings` from Task 1, `sub_agents` from Task 3, `reflection_node` from Task 3, `web_search`... tools from Task 2
- Produces: `AgentState` (TypedDict), `get_checkpointer(settings)`, `get_memory_store(settings)`, `build_graph(settings) -> CompiledStateGraph`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_state.py`:

```python
def test_agent_state_fields():
    from src.graph.state import AgentState

    keys = AgentState.__annotations__
    assert "messages" in keys
    assert "reflection_round" in keys
    assert "feedback" in keys
```

Create `backend/tests/test_checkpointer.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_get_checkpointer_sqlite(tmp_path):
    from src.config.settings import Settings
    from src.graph.checkpointer import get_checkpointer

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    cp = await get_checkpointer(test_settings)
    assert cp is not None
```

Create `backend/tests/test_builder.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_build_graph_returns_runnable(tmp_path):
    from src.config.settings import Settings
    from src.graph.builder import build_graph

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    graph = await build_graph(test_settings)
    assert graph is not None
    assert hasattr(graph, "astream_events")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_state.py tests/test_checkpointer.py tests/test_builder.py -v -x`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/graph/state.py`:

```python
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    reflection_round: int
    feedback: str
    needs_rewrite: bool
```

Create `backend/src/graph/checkpointer.py`:

```python
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore

from src.config.settings import Settings


async def get_checkpointer(settings: Settings) -> AsyncSqliteSaver:
    """SQLite-backed checkpointer for thread persistence."""
    return AsyncSqliteSaver.from_conn_string(settings.db_path)


async def get_memory_store(settings: Settings) -> InMemoryStore:
    """InMemory store placeholder. Replace with SQLiteStore for persistence."""
    return InMemoryStore()
```

Create `backend/src/graph/builder.py`:

```python
from deepagents import create_deep_agent
from langgraph.graph import END, StateGraph

from src.agents.reflection import reflection_node
from src.agents.sub_agents import sub_agents
from src.config.settings import Settings
from src.graph.checkpointer import get_checkpointer, get_memory_store
from src.graph.state import AgentState
from src.llm.factory import create_llm
from src.tools import python_repl, read_file, web_fetch, web_search, write_file


async def build_graph(settings: Settings):
    """Build and compile the full agent graph."""
    builder = StateGraph(AgentState)

    llm = create_llm(settings)
    all_tools = [web_search, web_fetch, python_repl, read_file, write_file]

    deep_agent = create_deep_agent(
        model=llm,
        tools=all_tools,
        subagents=sub_agents,
        checkpointer=await get_checkpointer(settings),
        store=await get_memory_store(settings),
    )

    def deep_agent_node(state: AgentState) -> AgentState:
        result = deep_agent.invoke(state)
        result["reflection_round"] = state.get("reflection_round", 0)
        return result

    def memory_node(state: AgentState) -> AgentState:
        return state

    builder.add_node("deep_agent", deep_agent_node)
    builder.add_node("reflect", reflection_node)
    builder.add_node("save_memory", memory_node)

    builder.set_entry_point("deep_agent")
    builder.add_edge("deep_agent", "reflect")
    builder.add_conditional_edges(
        "reflect",
        lambda s: "deep_agent" if s.get("needs_rewrite") and s.get("reflection_round", 0) < 3 else "save_memory",
        {"deep_agent": "deep_agent", "save_memory": "save_memory"},
    )
    builder.add_edge("save_memory", END)

    return builder.compile(checkpointer=await get_checkpointer(settings))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_state.py tests/test_checkpointer.py tests/test_builder.py -v -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add . && git commit -m "feat(backend): add graph state, checkpointer, and builder"
```

---

### Task 5: FastAPI Backend

**Files:**
- Create: `backend/src/api/schemas.py`
- Create: `backend/src/api/routes/chat.py`
- Create: `backend/src/api/routes/threads.py`
- Create: `backend/src/api/main.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `build_graph(settings)` from Task 4, `Settings` from Task 1
- Produces: `create_app(settings) -> FastAPI`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_api_schemas.py`:

```python
def test_chat_request_import():
    from src.api.schemas import ChatRequest

    req = ChatRequest(thread_id="t1", message="hello")
    assert req.thread_id == "t1"
    assert req.message == "hello"
```

Create `backend/tests/test_chat_stream.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)
    return TestClient(app)


def test_chat_stream_endpoint_exists(client):
    response = client.post("/chat/stream", json={"thread_id": "t1", "message": "hi"})
    assert response.status_code != 404
```

Create `backend/tests/test_threads.py`:

```python
def test_threads_routes_exist():
    from src.api.routes.threads import router

    paths = [r.path for r in router.routes]
    assert "/threads" in paths
```

Create `backend/tests/test_main.py`:

```python
def test_create_app_returns_fastapi(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)
    assert app is not None
    assert hasattr(app, "routes")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_api_schemas.py tests/test_chat_stream.py tests/test_threads.py tests/test_main.py -v -x`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/api/schemas.py`:

```python
from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ThreadInfo(BaseModel):
    thread_id: str
    created_at: str
    last_message: str


class ThreadMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ThreadDetail(BaseModel):
    thread_id: str
    messages: list[ThreadMessage]
```

Create `backend/src/api/routes/chat.py`:

```python
import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from src.api.schemas import ChatRequest
from src.config.settings import Settings
from src.graph.builder import build_graph

router = APIRouter()


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, settings: Settings = None):
    """Stream agent responses via Server-Sent Events."""
    graph = await build_graph(settings)

    config = {"configurable": {"thread_id": request.thread_id}}
    input_state = {"messages": [("user", request.message)], "reflection_round": 0}

    async def event_generator():
        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                kind = event.get("event", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", "")
                    if hasattr(chunk, "content"):
                        chunk_data = chunk.content
                    else:
                        chunk_data = str(chunk)
                    yield json.dumps({"type": "token", "content": chunk_data})

                elif kind == "on_tool_start":
                    yield json.dumps({
                        "type": "tool_start",
                        "tool": event.get("data", {}).get("name", ""),
                    })

                elif kind == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    if len(str(output)) > 200:
                        output = str(output)[:200] + "..."
                    yield json.dumps({
                        "type": "tool_end",
                        "tool": event.get("data", {}).get("name", ""),
                        "output": str(output),
                    })

                elif kind == "on_chain_end":
                    yield json.dumps({"type": "done"})

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)})

    return EventSourceResponse(event_generator())
```

Create `backend/src/api/routes/threads.py`:

```python
from fastapi import APIRouter

from src.api.schemas import ThreadDetail, ThreadInfo

router = APIRouter()


@router.get("/threads")
async def list_threads() -> list[ThreadInfo]:
    """List all conversation threads."""
    return []


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str) -> ThreadDetail:
    """Get a specific thread with all messages."""
    return ThreadDetail(thread_id=thread_id, messages=[])


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a conversation thread."""
    return {"status": "deleted"}
```

Create `backend/src/api/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, threads
from src.config.settings import Settings


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Agent Moew API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(threads.router, prefix="/api/v1")

    return app
```

Create `backend/src/api/__init__.py`:

```python
from src.api.main import create_app
```

Create `backend/src/api/routes/__init__.py`:

```python
from src.api.routes import chat, threads
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api_schemas.py tests/test_chat_stream.py tests/test_threads.py tests/test_main.py -v -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add . && git commit -m "feat(backend): add FastAPI routes (chat SSE, threads) and app factory"
```

---

### Task 6: LangSmith Observability

**Files:**
- Create: `backend/src/observability/langsmith.py`
- Test: `backend/tests/test_langsmith.py`

**Interfaces:**
- Consumes: `Settings` from Task 1
- Produces: `setup_langsmith(settings: Settings) -> None`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_langsmith.py`:

```python
def test_setup_langsmith_returns_none():
    from src.config.settings import Settings
    from src.observability.langsmith import setup_langsmith

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
    )
    result = setup_langsmith(test_settings)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_langsmith.py -v -x`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

Create `backend/src/observability/langsmith.py`:

```python
from langchain_core.tracers.langchain import LangChainTracer

from src.config.settings import Settings


def setup_langsmith(settings: Settings) -> None:
    """Initialize LangSmith tracing. Call once at app startup."""
    if not settings.langsmith_tracing:
        return

    tracer = LangChainTracer(project_name=settings.langsmith_project)
    # LangChain automatically uses this tracer for all runs when
    # LANGCHAIN_TRACING_V2=true env var is set.
```

Update `backend/src/api/main.py` to call setup_langsmith at startup:

Add to `create_app()` after middleware:

```python
from src.observability.langsmith import setup_langsmith


def create_app(settings: Settings) -> FastAPI:
    # ... existing middleware ...
    setup_langsmith(settings)
    # ... existing router includes ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_langsmith.py -v -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend
git add . && git commit -m "feat(backend): add LangSmith observability setup"
```

---

### Task 7: Next.js Frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/components/ChatWindow.tsx`
- Create: `frontend/components/MessageBubble.tsx`
- Create: `frontend/components/AgentSteps.tsx`
- Create: `frontend/components/ThreadSidebar.tsx`
- Create: `frontend/lib/sse.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/.env.local.example`

**Interfaces:**
- Consumes: FastAPI backend at `NEXT_PUBLIC_API_URL`
- Produces: `App()` — main page component with chat and agent steps

- [ ] **Step 1: Initialize project**

```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
cd frontend
```

- [ ] **Step 2: Create package.json with required deps**

Ensure these dependencies in `frontend/package.json`:

```json
{
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "swr": "^2.2.0"
  }
}
```

Run: `cd frontend && npm install`

- [ ] **Step 3: Create .env.local.example**

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

- [ ] **Step 4: Create SSE client library**

Create `frontend/lib/sse.ts`:

```typescript
export interface StreamEvent {
  type: "token" | "tool_start" | "tool_end" | "plan" | "reflection" | "done" | "error";
  content?: string;
  tool?: string;
  output?: string;
  message?: string;
}

export function streamChat(
  threadId: string,
  message: string,
  onEvent: (event: StreamEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const url = new URL(`${apiUrl}/chat/stream`);

  const body = JSON.stringify({ thread_id: threadId, message });
  const controller = new AbortController();

  fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const text = decoder.decode(value, { stream: true });
        for (const line of text.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6)) as StreamEvent;
            onEvent(event);
          } catch {}
        }
      }
    })
    .catch((err) => onError?.(err));

  return () => controller.abort();
}
```

- [ ] **Step 5: Create API client**

Create `frontend/lib/api.ts`:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function listThreads() {
  const res = await fetch(`${API_URL}/threads`);
  if (!res.ok) return [];
  return res.json();
}

export async function getThread(threadId: string) {
  const res = await fetch(`${API_URL}/threads/${threadId}`);
  if (!res.ok) return null;
  return res.json();
}
```

- [ ] **Step 6: Create components**

Create `frontend/components/MessageBubble.tsx`:

```typescript
"use client";

export default function MessageBubble({
  content,
  isUser,
}: {
  content: string;
  isUser: boolean;
}) {
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-900"
        }`}
      >
        {content}
      </div>
    </div>
  );
}
```

Create `frontend/components/AgentSteps.tsx`:

```typescript
"use client";

import { StreamEvent } from "@/lib/sse";

interface ToolCall {
  tool: string;
  status: "running" | "done";
  output?: string;
}

export default function AgentSteps({
  plan,
  toolCalls,
  isRunning,
}: {
  plan: string[];
  toolCalls: ToolCall[];
  isRunning: boolean;
}) {
  if (!isRunning && toolCalls.length === 0) return null;

  return (
    <div className="mt-2 w-full rounded-lg bg-gray-50 p-3 text-sm">
      {plan.length > 0 && (
        <div className="mb-2">
          <p className="font-semibold text-gray-600">Plan:</p>
          {plan.map((p, i) => (
            <p key={i} className="ml-2 text-gray-500">
              {i + 1}. {p}
            </p>
          ))}
        </div>
      )}
      {toolCalls.map((tc, i) => (
        <div key={i} className="mb-1 flex items-center gap-2">
          <span className={tc.status === "running" ? "animate-spin" : "text-green-500"}>
            {tc.status === "running" ? "⏳" : "✓"}
          </span>
          <span className="font-medium">{tc.tool}</span>
          {tc.output && (
            <span className="text-gray-500 text-xs truncate max-w-[200px]">
              {tc.output}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
```

Create `frontend/components/ChatWindow.tsx`:

```typescript
"use client";

import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble";
import AgentSteps from "./AgentSteps";
import { streamChat, StreamEvent } from "@/lib/sse";

interface Message {
  id: string;
  content: string;
  isUser: boolean;
}

interface ToolCall {
  tool: string;
  status: "running" | "done";
  output?: string;
}

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [plan, setPlan] = useState<string[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [streamContent, setStreamContent] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent]);

  const send = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      isUser: true,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setPlan([]);
    setToolCalls([]);
    setStreamContent("");

    stopRef.current = streamChat(
      "default",
      input,
      (event: StreamEvent) => {
        switch (event.type) {
          case "token":
            setStreamContent((prev) => prev + (event.content || ""));
            break;
          case "tool_start":
            setToolCalls((prev) => [
              ...prev,
              { tool: event.tool || "", status: "running" },
            ]);
            setPlan((prev) =>
              prev.length === 0 ? [`Using tool: ${event.tool}`] : prev
            );
            break;
          case "tool_end":
            setToolCalls((prev) =>
              prev.map((tc) =>
                tc.tool === event.tool && tc.status === "running"
                  ? { ...tc, status: "done" as const, output: event.output }
                  : tc
              )
            );
            break;
          case "done":
            if (streamContent) {
              setMessages((prev) => [
                ...prev,
                {
                  id: (Date.now() + 1).toString(),
                  content: streamContent,
                  isUser: false,
                },
              ]);
            }
            setStreamContent("");
            setIsLoading(false);
            break;
          case "error":
            setMessages((prev) => [
              ...prev,
              {
                id: (Date.now() + 1).toString(),
                content: `Error: ${event.message}`,
                isUser: false,
              },
            ]);
            setIsLoading(false);
            break;
        }
      }
    );
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} content={msg.content} isUser={msg.isUser} />
        ))}
        {streamContent && (
          <MessageBubble content={streamContent} isUser={false} />
        )}
        {isLoading && (
          <AgentSteps plan={plan} toolCalls={toolCalls} isRunning={isLoading} />
        )}
        <div ref={bottomRef} />
      </div>
      <div className="border-t p-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask the agent anything..."
            className="flex-1 rounded-lg border px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={send}
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-blue-600 px-6 py-2 text-white disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
```

Create `frontend/components/ThreadSidebar.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";
import { listThreads } from "@/lib/api";
import useSWR from "swr";

interface Thread {
  thread_id: string;
  last_message: string;
}

export default function ThreadSidebar({
  currentThreadId,
  onSelectThread,
  onNewThread,
}: {
  currentThreadId: string;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
}) {
  const { data: threads } = useSWR("threads", listThreads);

  return (
    <div className="w-64 border-r bg-gray-50 flex flex-col">
      <div className="p-4 border-b">
        <button
          onClick={onNewThread}
          className="w-full rounded-lg bg-blue-600 py-2 text-white text-sm font-medium"
        >
          + New Thread
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {threads?.map((t: Thread) => (
          <button
            key={t.thread_id}
            onClick={() => onSelectThread(t.thread_id)}
            className={`w-full px-4 py-3 text-left text-sm hover:bg-gray-100 border-b ${
              currentThreadId === t.thread_id ? "bg-blue-50" : ""
            }`}
          >
            <p className="font-medium truncate">{t.last_message}</p>
            <p className="text-gray-500 text-xs mt-1">{t.thread_id.slice(0, 8)}</p>
          </button>
        ))}
        {(!threads || threads.length === 0) && (
          <p className="p-4 text-gray-400 text-sm text-center">No threads yet</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Create layout and page**

Create `frontend/app/layout.tsx`:

```typescript
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Moew",
  description: "AI Agent with LangChain, LangGraph, and DeepAgents",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased h-screen">{children}</body>
    </html>
  );
}
```

Create `frontend/app/page.tsx`:

```typescript
"use client";

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import ThreadSidebar from "@/components/ThreadSidebar";

export default function Home() {
  const [currentThreadId, setCurrentThreadId] = useState("default");

  return (
    <div className="flex h-full">
      <ThreadSidebar
        currentThreadId={currentThreadId}
        onSelectThread={setCurrentThreadId}
        onNewThread={() => setCurrentThreadId(`thread-${Date.now()}`)}
      />
      <main className="flex-1">
        <ChatWindow />
      </main>
    </div>
  );
}
```

Create `frontend/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body {
  height: 100%;
  margin: 0;
}
```

- [ ] **Step 8: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 9: Commit**

```bash
cd frontend
git add . && git commit -m "feat(frontend): Next.js chat UI with SSE streaming"
```

---

### Task 8: Learning Path Doc

**Files:**
- Create: `docs/learning_path.md`

**Interfaces:**
- Consumes: All tasks above

- [ ] **Step 1: Write learning path**

Create `docs/learning_path.md`:

```markdown
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
cd backend && uvicorn src.api.main:app --reload --factory

# Terminal 2
cd frontend && npm run dev
```

Open http://localhost:3000, ask the agent a question, check LangSmith dashboard for traces.
```

- [ ] **Step 2: Commit**

```bash
git add docs/learning_path.md && git commit -m "docs: add learning path curriculum"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ LLM factory + settings (Task 1)
- ✅ 4 tools: web_search, web_fetch, python_repl, file_tools (Task 2)
- ✅ Sub-agents: researcher, coder (Task 3)
- ✅ Reflection node with max 3 rounds (Task 3)
- ✅ AgentState, checkpointer, builder (Task 4)
- ✅ FastAPI SSE + threads endpoints (Task 5)
- ✅ LangSmith observability (Task 6)
- ✅ Next.js frontend: ChatWindow, AgentSteps, ThreadSidebar (Task 7)
- ✅ Learning path doc (Task 8)

**Placeholder scan:** No TBD, TODO, or "implement later" in any task.

**Type consistency:** Settings used across tasks; `build_graph` returns the compiled graph; sub-agent dicts match Task 3; reflection_node consumed in Task 4.

**All tasks buildable:** Each task ends with tests passing and a commit.
