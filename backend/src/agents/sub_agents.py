from src.tools import python_repl, read_file, web_fetch, web_search, write_file

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

coder_subagent = {
    "name": "coder",
    "description": "Expert at writing, testing, and debugging Python code in a sandbox.",
    "system_prompt": (
        "You are a senior Python developer. "
        "Write clean, minimal, correct code. "
        "Always validate outputs with python_repl before returning. "
        "Use read_file and write_file to persist reasonable artifacts in workspace/."
    ),
    "tools": [python_repl, read_file, write_file],
}

sub_agents = [researcher_subagent, coder_subagent]
