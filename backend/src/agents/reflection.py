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

    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        content = getattr(last_msg, "content", str(last_msg))
        if content and len(str(content).strip()) > 0 and not str(content).startswith("Lỗi:"):
            return {
                "needs_rewrite": False,
                "feedback": "Output quality is good",
                "reflection_round": round_num + 1,
            }

    assessment = QualityAssessment(
        score=2,
        feedback="Output may be empty or incomplete",
        needs_rewrite=True,
    )
    return {
        "needs_rewrite": assessment.needs_rewrite,
        "feedback": assessment.feedback,
        "reflection_round": round_num + 1,
    }

