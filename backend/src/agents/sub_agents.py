from langchain_core.tools import tool
from src.tools import web_search


@tool
async def researcher_subagent(query: str) -> str:
    """Subagent chuyên nghiên cứu & tổng hợp thông tin sâu từ web. Sử dụng khi cần tìm kiếm và phân tích thông tin phức tạp."""
    results = await web_search.ainvoke({"query": query})
    return f"[Báo cáo từ Researcher Subagent cho '{query}']:\n{results}"


sub_agents = [researcher_subagent]

