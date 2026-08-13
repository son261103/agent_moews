from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from src.config.settings import settings


@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path


def _parse_frontmatter(text: str) -> dict:
    """Return frontmatter dict, or {} if missing/malformed."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4:].lstrip("\n")


class SkillRegistry:
    """Scan skills/*/SKILL.md and expose name/description/content."""

    def __init__(self, root: Path) -> None:
        self._skills: dict[str, SkillInfo] = {}
        for skill_dir in sorted(root.glob("*/")):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            text = skill_file.read_text(encoding="utf-8")
            fm = _parse_frontmatter(text)
            name = fm.get("name") or skill_dir.name
            description = fm.get("description", "")
            if not description:
                continue  # require description so the LLM can discover it
            self._skills[name] = SkillInfo(
                name=name, description=description, path=skill_file
            )

    def list_skills(self) -> list[SkillInfo]:
        return list(self._skills.values())

    def load(self, name: str) -> str:
        if name not in self._skills:
            raise KeyError(f"Skill not found: {name}")
        return _strip_frontmatter(self._skills[name].path.read_text(encoding="utf-8"))


@lru_cache
def get_skill_registry() -> SkillRegistry:
    """Cached for the process lifetime; skills added at runtime require a restart to be discovered."""
    return SkillRegistry(Path(settings.skills_dir))


def build_skills_discovery() -> str:
    """Discovery section for the system prompt: 'name: description' lines."""
    skills = get_skill_registry().list_skills()
    return "\n".join(f"{s.name}: {s.description}" for s in skills)
