from langchain_core.tools import tool
from langchain_tavily import TavilySearch


@tool
def web_search(query: str) -> str:
    """Search the web for information using Tavily API."""
    search = TavilySearch(max_results=5)
    results = search.invoke(query)
    return str(results)
