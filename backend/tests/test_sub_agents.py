def test_sub_agents_has_required_fields():
    from src.agents.sub_agents import sub_agents

    assert len(sub_agents) == 1
    for a in sub_agents:
        assert hasattr(a, "name")
        assert hasattr(a, "description")
        assert "researcher" in a.name

