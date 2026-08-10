from langchain_core.messages import trim_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES, RemoveMessage

from src.graph.state import AgentState

DEFAULT_MAX_CONTEXT_TOKENS = 8000


def trim_node(state: AgentState, config: dict) -> dict:
    """Trim conversation history to a token budget to avoid context overflow."""
    messages = state["messages"]
    configurable = config.get("configurable", {})
    max_tokens = configurable.get("max_context_tokens", DEFAULT_MAX_CONTEXT_TOKENS)
    token_counter = configurable.get("token_counter", "approximate")

    trimmed = trim_messages(
        messages,
        max_tokens=max_tokens,
        token_counter=token_counter,
        strategy="last",
        include_system=True,
        allow_partial=False,
    )

    # add_messages reducer appends; the sentinel deletes all existing messages
    # first so trimming replaces history instead of duplicating it.
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *trimmed]}
