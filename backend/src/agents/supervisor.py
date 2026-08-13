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
