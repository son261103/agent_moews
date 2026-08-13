from langchain_core.tools import tool

from src.skills.registry import get_skill_registry
from src.tools.registry import register_tool


@register_tool(group="skills")
@tool
def list_skills() -> str:
    """List available skills (format: 'name: description'). Call this to see what skills exist."""
    skills = get_skill_registry().list_skills()
    if not skills:
        return "Không có skill nào."
    return "\n".join(f"{s.name}: {s.description}" for s in skills)


@register_tool(group="skills")
@tool
def load_skill(name: str) -> str:
    """Load the full instructions of a skill by name so you can follow its workflow."""
    try:
        return get_skill_registry().load(name)
    except KeyError:
        return f"Skill not found: {name}"
