from deepagents import create_deep_agent
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from src.agents.reflection import reflection_node
from src.agents.sub_agents import sub_agents
from src.config.settings import Settings
from src.graph.checkpointer import get_checkpointer, get_memory_store
from src.graph.state import AgentState
from src.graph.trim import trim_node
from src.llm.factory import create_llm
from src.tools import get_current_time, get_news, get_weather, web_fetch, web_search


async def build_graph(settings: Settings):
    builder = StateGraph(AgentState)

    llm = create_llm(settings)
    all_tools = [web_search, web_fetch, get_current_time, get_news, get_weather]
    checkpointer = await get_checkpointer(settings)

    deep_agent = create_deep_agent(
        model=llm,
        tools=all_tools,
        subagents=sub_agents,
        checkpointer=checkpointer,
        store=await get_memory_store(settings),
    )

    async def deep_agent_node(state: AgentState, config: RunnableConfig) -> AgentState:
        thread_id = config["configurable"]["thread_id"]
        result = await deep_agent.ainvoke(
            state,
            config={"configurable": {"thread_id": thread_id}},
        )
        result["reflection_round"] = state.get("reflection_round", 0)
        return result

    def memory_node(state: AgentState) -> AgentState:
        return state

    builder.add_node("trim_history", trim_node)
    builder.add_node("deep_agent", deep_agent_node)
    builder.add_node("reflect", reflection_node)
    builder.add_node("save_memory", memory_node)

    builder.set_entry_point("trim_history")
    builder.add_edge("trim_history", "deep_agent")
    builder.add_edge("deep_agent", "reflect")
    builder.add_conditional_edges(
        "reflect",
        lambda s: "trim_history" if s.get("needs_rewrite") and s.get("reflection_round", 0) < 3 else "save_memory",
        {"trim_history": "trim_history", "save_memory": "save_memory"},
    )
    builder.add_edge("save_memory", END)

    return builder.compile(checkpointer=checkpointer)
