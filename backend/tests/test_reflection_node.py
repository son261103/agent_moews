def test_quality_assessment_schema():
    from src.agents.reflection import QualityAssessment
    from pydantic import BaseModel

    assert issubclass(QualityAssessment, BaseModel)
    fields = QualityAssessment.model_fields
    assert "score" in fields
    assert "feedback" in fields
    assert "needs_rewrite" in fields


def test_reflection_node_returns_needs_rewrite():
    from src.agents.reflection import reflection_node

    state = {"messages": [], "reflection_round": 0}
    result = reflection_node(state)

    assert result["needs_rewrite"] is True
    assert "feedback" in result
    assert result["reflection_round"] == 1


def test_reflection_node_max_rounds():
    from src.agents.reflection import reflection_node

    state = {"messages": [], "reflection_round": 3}
    result = reflection_node(state)

    assert result["needs_rewrite"] is False
    assert "Max" in result["feedback"]
    assert result["reflection_round"] == 3


def test_reflection_node_increments_round():
    from src.agents.reflection import reflection_node

    state = {"messages": [], "reflection_round": 2}
    result = reflection_node(state)

    assert result["needs_rewrite"] is True
    assert result["reflection_round"] == 3
