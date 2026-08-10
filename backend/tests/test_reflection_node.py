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

    assert "needs_rewrite" in result
    assert "feedback" in result
