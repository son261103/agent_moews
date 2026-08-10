def test_sub_agents_has_required_fields():
    from src.agents.sub_agents import sub_agents

    assert len(sub_agents) >= 2
    names = [a["name"] for a in sub_agents]
    assert "researcher" in names
    assert "coder" in names
    for a in sub_agents:
        assert "name" in a
        assert "description" in a
        assert "system_prompt" in a
        assert "tools" in a
