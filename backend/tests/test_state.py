def test_agent_state_fields():
    from src.graph.state import AgentState

    keys = AgentState.__annotations__
    assert "messages" in keys
    assert "reflection_round" in keys
    assert "feedback" in keys
