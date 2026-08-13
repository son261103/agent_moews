# Tool Registry + Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace manual tool declaration with a decorator-based registry, and restructure the graph so the main LLM (supervisor) only sees one tool per domain group (sub-agent), with each sub-agent a `create_react_agent` graph that binds only its group's tools.

**Architecture:** `src/tools/registry.py` provides `ToolRegistry` (class) + module singleton with `register_tool`/`get_all_tools`/`get_tools_by_group`/`get_groups`. Tool modules self-register via `@register_tool(group=...)`. `src/agents/supervisor.py` builds one wrapped `create_react_agent` tool per group; `builder.py` binds only those sub-agent tools to the supervisor LLM. Graph scaffolding (trim/reflect/save_memory/checkpointer) is unchanged. `src/agents/sub_agents.py` (redundant `researcher_subagent` wrapper) is deleted.

**Tech Stack:** Python 3.12, langgraph 1.2.10, langchain-core 1.5.3 (`.venv` at `backend/.venv`), pytest + pytest-asyncio (`asyncio_mode = "auto"`).

## Global Constraints

- All commands run from `backend/` directory using `.venv/bin/python -m pytest`.
- Tool groups: `research` = {web_search, web_fetch}, `info` = {get_current_time, get_news, get_weather}.
- Sub-agent tool names must follow `f"{group}_agent"` (e.g. `research_agent`, `info_agent`).
- Registry duplicate tool names raise `ValueError("Duplicate tool name registered: ...")` at registration time.
- Do NOT modify `src/graph/trim.py`, `src/graph/state.py`, `src/agents/reflection.py`, `src/tools/truncate.py` — out of scope.
- No new dependencies; `create_react_agent` comes from `langgraph.prebuilt`.
- Tests import modules inside test functions (existing repo convention, see `tests/test_builder.py`).

---

### Task 1: Tool registry

**Files:**
- Create: `src/tools/registry.py`
- Create: `tests/test_registry.py`

**Interfaces:**
- Consumes: nothing (only `langchain_core.tools.BaseTool`, `tool`)
- Produces:
  - `class ToolRegistry` with methods `register(group: str, name: str | None = None) -> Callable[[BaseTool], BaseTool]`, `all_tools() -> list[BaseTool]`, `tools_by_group(group: str) -> list[BaseTool]`, `groups() -> list[str]`
  - Module-level singleton: `registry = ToolRegistry()`
  - Module-level convenience bindings: `register_tool = registry.register`, `get_all_tools = registry.all_tools`, `get_tools_by_group = registry.tools_by_group`, `get_groups = registry.groups`

- [ ] **Step 1: Write the failing test** — create `tests/test_registry.py`:

```python
import pytest
from langchain_core.tools import tool

from src.tools.registry import ToolRegistry


def test_register_and_query_groups():
    reg = ToolRegistry()

    @reg.register(group="research")
    @tool
    def fake_search(query: str) -> str:
        """Search fake."""
        return ""

    @reg.register(group="info")
    @tool
    def fake_time() -> str:
        """Time fake."""
        return ""

    assert {t.name for t in reg.all_tools()} == {"fake_search", "fake_time"}
    assert [t.name for t in reg.tools_by_group("research")] == ["fake_search"]
    assert [t.name for t in reg.tools_by_group("info")] == ["fake_time"]
    assert reg.groups() == ["research", "info"]


def test_register_keeps_registration_order():
    reg = ToolRegistry()

    @reg.register(group="info")
    @tool
    def fake_time() -> str:
        """Time fake."""
        return ""

    @reg.register(group="research")
    @tool
    def fake_search(query: str) -> str:
        """Search fake."""
        return ""

    assert reg.groups() == ["info", "research"]


def test_duplicate_name_raises():
    reg = ToolRegistry()

    @reg.register(group="research")
    @tool
    def fake_search(query: str) -> str:
        """Search fake."""
        return ""

    with pytest.raises(ValueError, match="Duplicate tool name registered"):

        @reg.register(group="info")
        @tool
        def fake_search(query: str) -> str:
            """Search fake again."""
            return ""


def test_custom_name_override():
    reg = ToolRegistry()

    @reg.register(group="info", name="custom_name")
    @tool
    def fake_time() -> str:
        """Time fake."""
        return ""

    assert reg.all_tools()[0].name == "custom_name"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.tools.registry'`

- [ ] **Step 3: Write minimal implementation** — create `src/tools/registry.py`:

```python
from typing import Callable

from langchain_core.tools import BaseTool


class ToolRegistry:
    """Collect @tool objects and tag them with a domain group."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._groups: dict[str, str] = {}

    def register(
        self, group: str, name: str | None = None
    ) -> Callable[[BaseTool], BaseTool]:
        """Decorator factory: `@registry.register(group="info")` above `@tool`."""

        def decorator(tool_obj: BaseTool) -> BaseTool:
            tool_name = name or tool_obj.name
            if tool_name in self._tools:
                raise ValueError(f"Duplicate tool name registered: {tool_name}")
            self._tools[tool_name] = tool_obj
            self._groups[tool_name] = group
            return tool_obj

        return decorator

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def tools_by_group(self, group: str) -> list[BaseTool]:
        return [t for name, t in self._tools.items() if self._groups[name] == group]

    def groups(self) -> list[str]:
        seen: list[str] = []
        for group in self._groups.values():
            if group not in seen:
                seen.append(group)
        return seen


# Module-level singleton used by application code.
registry = ToolRegistry()
register_tool = registry.register
get_all_tools = registry.all_tools
get_tools_by_group = registry.tools_by_group
get_groups = registry.groups
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_registry.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/tools/registry.py tests/test_registry.py
git commit -m "feat(tools): add ToolRegistry with group-based registration"
```

---

### Task 2: Auto-register existing tools

**Files:**
- Modify: `src/tools/__init__.py` (replace manual imports with auto-import loop)
- Modify: `src/tools/web_search.py` (add `@register_tool(group="research")`)
- Modify: `src/tools/web_fetch.py` (add `@register_tool(group="research")`)
- Modify: `src/tools/time_tools.py` (add `@register_tool(group="info")`)
- Modify: `src/tools/news_tools.py` (add `@register_tool(group="info")`)
- Modify: `src/tools/weather_tools.py` (add `@register_tool(group="info")`)
- Create: `tests/test_tools_registry.py`

**Interfaces:**
- Consumes: `register_tool`, `get_all_tools`, `get_tools_by_group`, `get_groups` from `src.tools.registry` (Task 1)
- Produces: importing `src.tools` registers exactly the 5 real tools in groups `research`/`info`

- [ ] **Step 1: Write the failing test** — create `tests/test_tools_registry.py`:

```python
def test_real_tools_registered_in_groups():
    from src.tools import get_all_tools, get_groups, get_tools_by_group

    names = {t.name for t in get_all_tools()}
    assert names == {
        "web_search",
        "web_fetch",
        "get_current_time",
        "get_news",
        "get_weather",
    }
    assert set(get_groups()) == {"research", "info"}
    assert {t.name for t in get_tools_by_group("research")} == {"web_search", "web_fetch"}
    assert {t.name for t in get_tools_by_group("info")} == {
        "get_current_time",
        "get_news",
        "get_weather",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tools_registry.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_all_tools' from 'src.tools'`

- [ ] **Step 3: Implement** — replace the entire content of `src/tools/__init__.py`:

```python
import pkgutil
from importlib import import_module

from src.tools.registry import get_all_tools, get_groups, get_tools_by_group, register_tool

# Import every module under src/tools so their @register_tool decorators run.
# truncate.py and registry.py import fine and register nothing.
for _module in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
    if _module.name != "registry":
        import_module(f"{__name__}.{_module.name}")

__all__ = ["register_tool", "get_all_tools", "get_tools_by_group", "get_groups"]
```

Add the decorator to each tool file. In **each** of the 5 files, add this import after the existing `from langchain_core.tools import tool` line:

```python
from src.tools.registry import register_tool
```

and place `@register_tool(group="...")` directly ABOVE the existing `@tool` line, with the group per file:

- `web_search.py` → `group="research"`
- `web_fetch.py` → `group="research"`
- `time_tools.py` → `group="info"`
- `news_tools.py` → `group="info"`
- `weather_tools.py` → `group="info"`

Example result for `src/tools/web_search.py` (other files follow the same pattern with their own group):

```python
from src.tools.registry import register_tool
from src.tools.truncate import truncate_text


@register_tool(group="research")
@tool
def web_search(query: str) -> str:
    """Search the web for information using Tavily API."""
    ...
```

Do NOT add decorators to `src/tools/truncate.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tools_registry.py -v`
Expected: 1 PASSED

- [ ] **Step 5: Run existing tool tests to verify no regression**

Run: `.venv/bin/python -m pytest tests/test_tools.py tests/test_truncate.py -q`
Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add src/tools/ tests/test_tools_registry.py
git commit -m "feat(tools): auto-register existing tools via decorator registry"
```

---

### Task 3: Sub-agent factory

**Files:**
- Create: `src/agents/supervisor.py` (part 1: `create_sub_agent`)
- Create: `tests/test_supervisor.py`

**Interfaces:**
- Consumes: `langgraph.prebuilt.create_react_agent`, `langchain_core.tools.tool`, `langchain_core.messages.HumanMessage/AIMessage`
- Produces: `create_sub_agent(name: str, description: str, tools: list[BaseTool], llm) -> BaseTool` — an async `@tool` whose invocation runs the ReAct graph with a `HumanMessage(query)` and returns the last non-empty `AIMessage` content

- [ ] **Step 1: Write the failing test** — create `tests/test_supervisor.py`:

```python
import pytest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage


@pytest.mark.asyncio
async def test_create_sub_agent_returns_final_ai_message():
    from src.agents.supervisor import create_sub_agent

    fake_graph = MagicMock()
    fake_graph.ainvoke.return_value = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="final answer")]
    }
    fake_llm = MagicMock()
    fake_tools = [MagicMock(), MagicMock()]

    with patch("src.agents.supervisor.create_react_agent", return_value=fake_graph) as mock_cra:
        agent_tool = create_sub_agent(
            name="research_agent",
            description="Research things",
            tools=fake_tools,
            llm=fake_llm,
        )

    assert agent_tool.name == "research_agent"
    assert agent_tool.description == "Research things"
    result = await agent_tool.ainvoke({"query": "tim kiem"})
    assert result == "final answer"
    mock_cra.assert_called_once_with(model=fake_llm, tools=fake_tools)
    called_input = fake_graph.ainvoke.call_args.args[0]
    assert isinstance(called_input["messages"][0], HumanMessage)
    assert called_input["messages"][0].content == "tim kiem"


@pytest.mark.asyncio
async def test_create_sub_agent_skips_tool_message_when_ended_on_tool():
    from src.agents.supervisor import create_sub_agent

    fake_graph = MagicMock()
    fake_graph.ainvoke.return_value = {
        "messages": [
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}]),
            AIMessage(content="real answer"),
        ]
    }

    with patch("src.agents.supervisor.create_react_agent", return_value=fake_graph):
        agent_tool = create_sub_agent(
            name="info_agent",
            description="Info things",
            tools=[MagicMock()],
            llm=MagicMock(),
        )

    result = await agent_tool.ainvoke({"query": "gio"})
    assert result == "real answer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_supervisor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.agents.supervisor'`

- [ ] **Step 3: Write minimal implementation** — create `src/agents/supervisor.py`:

```python
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent


def create_sub_agent(
    name: str, description: str, tools: list[BaseTool], llm
) -> BaseTool:
    """Wrap a ReAct sub-agent graph as a single tool the supervisor can call."""
    graph = create_react_agent(model=llm, tools=tools)

    @tool(name=name, description=description)
    async def sub_agent_tool(query: str) -> str:
        result = await graph.ainvoke({"messages": [HumanMessage(content=query)]})
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and getattr(msg, "content", ""):
                return str(msg.content)
        return "Sub-agent không tạo được câu trả lời."

    return sub_agent_tool
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_supervisor.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/agents/supervisor.py tests/test_supervisor.py
git commit -m "feat(agents): add create_sub_agent wrapping ReAct graph as tool"
```

---

### Task 4: Supervisor tool builder

**Files:**
- Modify: `src/agents/supervisor.py` (add `build_supervisor_tools` + `GROUP_DESCRIPTIONS`)
- Modify: `tests/test_supervisor.py` (add builder tests)

**Interfaces:**
- Consumes: `create_sub_agent` (Task 3), `get_groups`/`get_tools_by_group` from `src.tools.registry` (Task 1)
- Produces: `build_supervisor_tools(llm) -> list[BaseTool]` — one sub-agent tool per registered group, named `f"{group}_agent"`

- [ ] **Step 1: Write the failing test** — append to `tests/test_supervisor.py`:

```python
def test_build_supervisor_tools_one_per_group():
    from src.agents.supervisor import build_supervisor_tools

    fake_llm = MagicMock()
    with patch("src.agents.supervisor.create_react_agent") as mock_cra:
        tools = build_supervisor_tools(fake_llm)

    assert {t.name for t in tools} == {"research_agent", "info_agent"}
    assert all(t.description for t in tools)
    assert mock_cra.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_supervisor.py -v`
Expected: FAIL with `AttributeError: module 'src.agents.supervisor' has no attribute 'build_supervisor_tools'`

- [ ] **Step 3: Implement** — append to `src/agents/supervisor.py` (keep `create_sub_agent` from Task 3):

```python
from src.tools.registry import get_groups, get_tools_by_group

GROUP_DESCRIPTIONS = {
    "research": (
        "Chuyên nghiên cứu, tìm kiếm và tổng hợp thông tin trên web. "
        "Dùng khi cần tìm kiếm web hoặc đọc nội dung trang web."
    ),
    "info": (
        "Trả lời nhanh thông tin tiện ích: thời gian hiện tại, tin tức, "
        "thời tiết. Dùng cho các câu hỏi thông tin đơn giản."
    ),
}


def build_supervisor_tools(llm) -> list[BaseTool]:
    """One sub-agent tool per registered tool group."""
    return [
        create_sub_agent(
            name=f"{group}_agent",
            description=GROUP_DESCRIPTIONS.get(
                group, f"Chuyên xử lý yêu cầu thuộc nhóm '{group}'."
            ),
            tools=get_tools_by_group(group),
            llm=llm,
        )
        for group in get_groups()
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_supervisor.py -v`
Expected: 3 PASSED (2 from Task 3 + 1 new)

- [ ] **Step 5: Commit**

```bash
git add src/agents/supervisor.py tests/test_supervisor.py
git commit -m "feat(agents): add build_supervisor_tools creating one sub-agent per group"
```

---

### Task 5: Rewire graph to supervisor + remove legacy sub_agents

**Files:**
- Modify: `src/graph/builder.py` (bind supervisor tools instead of all tools)
- Modify: `tests/test_builder.py` (add supervisor wiring assertion)
- Delete: `src/agents/sub_agents.py`
- Delete: `tests/test_sub_agents.py`

**Interfaces:**
- Consumes: `build_supervisor_tools` from `src.agents.supervisor` (Task 4)
- Produces: `build_graph(settings)` whose agent node binds only the sub-agent tools; `ToolNode` runs the same sub-agent tools

- [ ] **Step 1: Write the failing test** — append to `tests/test_builder.py`:

```python
@pytest.mark.asyncio
async def test_build_graph_uses_supervisor_tools(tmp_path):
    from unittest.mock import patch

    from langchain_core.tools import tool

    from src.config.settings import Settings
    from src.graph.builder import build_graph

    @tool
    def fake_research_tool(query: str) -> str:
        """Fake research."""
        return ""

    @tool
    def fake_info_tool(query: str) -> str:
        """Fake info."""
        return ""

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    fake_tools = [fake_research_tool, fake_info_tool]
    with patch(
        "src.graph.builder.build_supervisor_tools", return_value=fake_tools
    ) as mock_build:
        graph = await build_graph(test_settings)

    mock_build.assert_called_once()
    assert graph is not None
    await graph.checkpointer.conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_builder.py -v`
Expected: FAIL with `AttributeError: module 'src.graph.builder' has no attribute 'build_supervisor_tools'`

- [ ] **Step 3: Implement** — modify `src/graph/builder.py`:

Replace the import block (lines 1-13) with:

```python
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.agents.reflection import reflection_node
from src.agents.supervisor import build_supervisor_tools
from src.config.settings import Settings
from src.graph.checkpointer import get_checkpointer
from src.graph.state import AgentState
from src.graph.trim import trim_node
from src.llm.factory import create_llm
```

Replace the tool setup block (lines 19-22) with:

```python
    llm = create_llm(settings)
    supervisor_tools = build_supervisor_tools(llm)
    llm_with_tools = llm.bind_tools(supervisor_tools)
    tool_node = ToolNode(supervisor_tools)
```

Everything else in `builder.py` (agent_node, should_continue, memory_node, node registration, edges, compile) stays exactly as-is.

- [ ] **Step 4: Delete legacy files**

```bash
git rm src/agents/sub_agents.py tests/test_sub_agents.py
```

- [ ] **Step 5: Run all tests to verify**

Run: `.venv/bin/python -m pytest -q`
Expected: ALL PASSED (no failures; the `test_sub_agents.py` file is gone)

- [ ] **Step 6: Commit**

```bash
git add src/graph/builder.py tests/test_builder.py
git commit -m "refactor(graph): bind supervisor sub-agent tools, drop legacy sub_agents"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run the full test suite once more**

Run: `.venv/bin/python -m pytest -q`
Expected: all PASSED

- [ ] **Step 2: Smoke-check that the app imports and graph builds**

Run:

```bash
.venv/bin/python -c "
import asyncio
from src.config.settings import Settings
from src.graph.builder import build_graph

async def main():
    graph = await build_graph(Settings(openai_api_key='sk-test', db_path='/tmp/smoke.db'))
    print('graph OK')
    await graph.checkpointer.conn.close()

asyncio.run(main())
"
```

Expected: prints `graph OK` with no exceptions.

- [ ] **Step 3: Verify git state is clean**

Run: `git status --short`
Expected: no modified files (all committed)
