from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages

from src.graph.trim import trim_node


def _state():
    messages = [
        SystemMessage("s"),
        HumanMessage("aaa"),
        AIMessage("bbb"),
        HumanMessage("ccc"),
        AIMessage("ddd"),
        HumanMessage("eee"),
    ]
    return {
        "messages": messages,
        "reflection_round": 0,
        "feedback": "",
        "needs_rewrite": False,
    }


def _counter(msgs):
    return sum(len(m.content) for m in msgs)


def _merged(state, result):
    """Apply the add_messages reducer exactly as LangGraph does."""
    return add_messages(state["messages"], result["messages"])


def test_trim_node_keeps_messages_when_under_budget():
    state = _state()
    result = trim_node(
        state,
        {"configurable": {"max_context_tokens": 1000, "token_counter": _counter}},
    )
    assert _merged(state, result) == state["messages"]


def test_trim_node_keeps_system_and_recent_messages():
    state = _state()
    result = trim_node(
        state,
        {"configurable": {"max_context_tokens": 8, "token_counter": _counter}},
    )
    contents = [m.content for m in _merged(state, result)]
    assert contents == ["s", "ddd", "eee"]


def test_trim_node_replaces_messages_instead_of_appending():
    state = _state()
    result = trim_node(
        state,
        {"configurable": {"max_context_tokens": 8, "token_counter": _counter}},
    )
    merged = _merged(state, result)
    assert len(merged) == 3
    assert [m.content for m in merged] == ["s", "ddd", "eee"]


def test_trim_node_uses_default_budget_when_not_configured():
    state = _state()
    result = trim_node(state, {})
    assert _merged(state, result) == state["messages"]
