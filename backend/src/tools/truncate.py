MAX_TOOL_OUTPUT_CHARS = 4000


def truncate_text(text: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Truncate long tool output to keep the LLM context window bounded."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated {len(text) - max_chars} chars]"

