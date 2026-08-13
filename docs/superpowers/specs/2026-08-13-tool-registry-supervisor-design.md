# Design: Tool Registry + Supervisor Architecture

Date: 2026-08-13
Status: Approved by user

## Problem

Tools are declared manually in two places:

1. `src/tools/__init__.py` — hand-written imports + `__all__`
2. `src/graph/builder.py` — hand-written `all_tools = [web_search, ...] + sub_agents`

Adding one tool requires editing both files. As the tool count grows (user anticipates
many more tools), the LLM in the single agent node gets bound to all tools at once,
which degrades tool-selection quality beyond ~10-20 tools.

## Goal

- Adding a tool = adding one file with a `@register_tool` decorator, no other edits.
- Supervisor pattern: the main graph's LLM only sees one tool per domain group
  (sub-agent). Each sub-agent binds only its group's tools.
- Keep the existing graph scaffolding (trim_history / reflect / save_memory /
  checkpointer) intact.

## Architecture

```
Graph chính (builder.py — khung trim/reflect/save_memory/checkpointer giữ nguyên)
      │
      ▼
┌─────────────┐   bind 2 tool (sub-agent)    ┌────────────────┐
│  supervisor │ ───────────────────────────► │    tools       │
│   (LLM)     │                              │  (ToolNode)    │
└─────────────┘                              └───────┬────────┘
                                                     ▼ chạy sub-agent graph
                        ┌────────────────────────────┴─────────────────────────┐
                        ▼                                                       ▼
              ┌───────────────────┐                                  ┌───────────────────┐
              │  research_agent   │                                  │    info_agent     │
              │  (ReAct graph)    │                                  │  (ReAct graph)    │
              │  web_search       │                                  │  get_current_time │
              │  web_fetch        │                                  │  get_news         │
              │  (+tool mới sau)  │                                  │  get_weather      │
              └───────────────────┘                                  └───────────────────┘
```

## Components

### 1. `src/tools/registry.py` (new)

- `@register_tool(group=...)` — decorator; name defaults to the function name
  (optional override `@register_tool("custom_name", group=...)`); stores the
  `@tool`-wrapped tool object in a dict keyed by name, tagged with group.
- `get_all_tools() -> list[BaseTool]` — all registered tools
- `get_tools_by_group(group: str) -> list[BaseTool]`
- `get_groups() -> list[str]` — distinct group names in registration order

### 2. Tool files — one added decorator line

```python
from src.tools.registry import register_tool

@register_tool(group="research")
@tool
def web_search(query: str) -> str: ...
```

`src/tools/__init__.py` changes to auto-import every module under `src/tools/`
(via `pkgutil.iter_modules`) so the decorators always run. Non-tool modules such as
`truncate.py` are imported harmlessly (they register nothing).

### 3. `src/agents/supervisor.py` (new)

- `create_sub_agent(name, description, tools, llm) -> BaseTool`
  - Builds a ReAct graph with `create_react_agent` from `langgraph.prebuilt`
  - Wraps it in an async `@tool`; description drives the supervisor's selection
  - Sub-agent graph is ephemeral (no checkpointer); `create_react_agent` has a
    default recursion limit (~25) so it cannot loop forever
- `build_supervisor_tools(llm) -> list[BaseTool]`
  - Reads the registry, creates one sub-agent tool per group

### 4. `src/graph/builder.py` — minimal changes

- `agent_node` binds `build_supervisor_tools(llm)` instead of all tools
- `ToolNode` receives the same sub-agent tools
- trim/reflect/save_memory/checkpointer structure unchanged

### 5. Remove `researcher_subagent` (`src/agents/sub_agents.py`)

Redundant wrapper (it only called `web_search` internally). Research group now
contains `web_search` + `web_fetch` directly. The `sub_agents.py` file is deleted;
sub-agent tools are built dynamically by `supervisor.py`.

## Groups (initial)

| Group | Tools |
|---|---|
| `research` | web_search, web_fetch |
| `info` | get_current_time, get_news, get_weather |

Future domains: add a new group string — the supervisor automatically gets a new
sub-agent tool. No graph changes.

## Error handling / safety

- Sub-agent loops bounded by `create_react_agent` recursion limit.
- Supervisor reflection (`reflect` node) still validates final output quality with
  `reflection_round < 3` bound.
- Registry failures (duplicate name) should raise at import time — fail fast.

## Testing

- Registry unit test: decorator registration, group queries, duplicate-name error.
- Supervisor test: `build_supervisor_tools` returns one tool per group with correct
  bound tools (inspect wrapped graph), description non-empty.
- Builder test: graph compiles and supervisor node's bound tools are the sub-agents.
