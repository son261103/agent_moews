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


async def build_graph(settings: Settings):
    builder = StateGraph(AgentState)

    llm = create_llm(settings)
    supervisor_tools = build_supervisor_tools(llm)
    llm_with_tools = llm.bind_tools(supervisor_tools)
    tool_node = ToolNode(supervisor_tools)
    checkpointer = await get_checkpointer(settings)

    # 1. Primary ReAct Agent Node
    async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        messages = state["messages"]
        system_msg = SystemMessage(
            content=(
                "Bạn là Agent Moew, một trợ lý AI thông minh được xây dựng 100% bằng LangGraph. "
                "Hãy tự động chọn và thực thi các công cụ (tools) hoặc subagent khi cần thiết để hỗ trợ người dùng."
            )
        )
        has_system = any(isinstance(m, SystemMessage) for m in messages)
        full_messages = [system_msg] + messages if not has_system else messages
        response = await llm_with_tools.ainvoke(full_messages, config=config)
        return {"messages": [response]}

    # 2. Conditional Router: checks if LLM requested tool execution
    def should_continue(state: AgentState) -> str:
        messages = state.get("messages", [])
        if not messages:
            return "reflect"
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "reflect"

    # Add Nodes to Graph
    builder.add_node("trim_history", trim_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("reflect", reflection_node)

    # Define Workflow Edges & Control Flow
    builder.set_entry_point("trim_history")
    builder.add_edge("trim_history", "agent")

    # Conditional Edge: agent -> tools (if tool calls) OR agent -> reflect (if final response)
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "reflect": "reflect",
        },
    )

    # Tool execution loops back to agent node
    builder.add_edge("tools", "agent")

    # Reflection & Self-Correction Edge
    builder.add_conditional_edges(
        "reflect",
        lambda s: "trim_history" if s.get("needs_rewrite") and s.get("reflection_round", 0) < 3 else END,
        {"trim_history": "trim_history", END: END},
    )

    return builder.compile(checkpointer=checkpointer)

