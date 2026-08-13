from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import create_react_agent


def create_sub_agent(
    name: str, description: str, tools: list[BaseTool], llm
) -> BaseTool:
    """Wrap a ReAct sub-agent graph as a single tool the supervisor can call."""
    graph = create_react_agent(model=llm, tools=tools)

    @tool(name, description=description)
    async def sub_agent_tool(query: str) -> str:
        result = await graph.ainvoke({"messages": [HumanMessage(content=query)]})
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and getattr(msg, "content", ""):
                return str(msg.content)
        return "Sub-agent không tạo được câu trả lời."

    return sub_agent_tool
