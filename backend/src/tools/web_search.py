import json

from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from src.tools.truncate import truncate_text


@tool
def web_search(query: str) -> str:
    """Search the web for information using Tavily API."""
    search = TavilySearch(max_results=5)
    results = search.invoke(query)
    if isinstance(results, (dict, list)):
        text = json.dumps(results, indent=2, ensure_ascii=False)
    else:
        text = str(results)
    return truncate_text(text)

