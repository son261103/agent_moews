"""DB-backed skill registry (skills stored via AdminStore, not files)."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import yaml

from src.config.settings import settings


@dataclass
class SkillInfo:
    name: str
    description: str
    content: str = ""
    path: Path | None = None


def parse_frontmatter(text: str) -> dict:
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


class SkillRegistry:
    """Expose skills stored in the DB (via AdminStore)."""

    def __init__(self, store_factory: Callable[[], "AdminStore"]) -> None:
        self._store_factory = store_factory
        self._store: "AdminStore | None" = None

    async def _ensure_store(self) -> "AdminStore":
        if self._store is None:
            from src.api.admin_store import AdminStore

            self._store = self._store_factory()
            await self._store.connect()
        return self._store

    async def list_skills(self) -> list[SkillInfo]:
        store = await self._ensure_store()
        return await store.list_skills()

    async def load(self, name: str) -> str:
        store = await self._ensure_store()
        skill = await store.get_skill(name)
        if skill is None:
            raise KeyError(f"Skill not found: {name}")
        return skill.content


def _default_store_factory() -> "AdminStore":
    from src.api.admin_store import AdminStore

    return AdminStore(settings.db_path)


@lru_cache
def get_skill_registry() -> SkillRegistry:
    """Cached for the process lifetime; DB queries run per call, so new/edited
    skills are visible immediately. Point at a different DB via settings.db_path
    and call get_skill_registry.cache_clear()."""
    return SkillRegistry(_default_store_factory)


async def build_skills_discovery() -> str:
    """Discovery section for the system prompt: 'name: description' lines."""
    skills = await get_skill_registry().list_skills()
    return "\n".join(f"{s.name}: {s.description}" for s in skills)
