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
