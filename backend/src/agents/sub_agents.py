from src.tools import web_fetch, web_search

researcher_subagent = {
    "name": "researcher",
    "description": "Expert at finding, fetching, and synthesizing information from the web.",
    "system_prompt": (
        "You are a research specialist. "
        "For any research task: search the web with web_search, "
        "fetch relevant pages with web_fetch, synthesize findings into clear notes, "
        "and always cite sources."
    ),
    "tools": [web_search, web_fetch],
}

sub_agents = [researcher_subagent]
