from pydantic import BaseModel, Field


class QualityAssessment(BaseModel):
    score: int = Field(..., ge=1, le=5, description="Quality score 1-5")
    feedback: str = Field(default="", description="Detailed feedback if score is low")
    needs_rewrite: bool = Field(default=False)


def reflection_node(state: dict) -> dict:
    """Evaluate output quality. Returns needs_rewrite + feedback + next round."""
    round_num = state.get("reflection_round", 0)

    if round_num >= 3:
        return {
            "needs_rewrite": False,
            "feedback": "Max reflection rounds reached",
            "reflection_round": round_num,
        }

    # Placeholder: in production this would use an LLM to evaluate quality.
    # For now it always requests one rewrite so the loop has a chance to improve.
    assessment = QualityAssessment(
        score=3,
        feedback="Output may be incomplete or unclear",
        needs_rewrite=True,
    )
    return {
        "needs_rewrite": assessment.needs_rewrite,
        "feedback": assessment.feedback,
        "reflection_round": round_num + 1,
    }
