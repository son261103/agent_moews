from src.skills.registry import build_skills_discovery, get_skill_registry
from src.tools.registry import register_tool
from langchain_core.tools import tool


@register_tool(group="skills")
@tool
async def list_skills() -> str:
    """List available skills as 'name: description' lines."""
    discovery = await build_skills_discovery()
    return discovery if discovery else "Không có skill nào."


@register_tool(group="skills")
@tool
async def load_skill(name: str) -> str:
    """Load a skill's full instructions by name. Returns the skill body."""
    try:
        return await get_skill_registry().load(name)
    except KeyError:
        return f"Skill not found: {name}"
