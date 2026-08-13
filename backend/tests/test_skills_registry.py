import asyncio

import pytest

from src.api.admin_store import AdminStore
from src.skills.registry import build_skills_discovery, parse_frontmatter


def _reg(tmp_path):
    """Return a registry wired to a fresh DB."""
    from src.skills.registry import get_skill_registry

    import src.config.settings as settings_module

    settings_module.settings.db_path = str(tmp_path / "skills.db")
    get_skill_registry.cache_clear()
    return get_skill_registry()


def test_list_skills_sorted_and_load(tmp_path):
    reg = _reg(tmp_path)
    store = AdminStore(str(tmp_path / "skills.db"))
    asyncio.run(store.connect())
    asyncio.run(store.create_skill("beta", "B skill", "body-b"))
    asyncio.run(store.create_skill("alpha", "A skill", "body-a"))
    asyncio.run(store.close())

    skills = asyncio.run(reg.list_skills())
    assert [s.name for s in skills] == ["alpha", "beta"]
    assert asyncio.run(reg.load("alpha")) == "body-a"


def test_load_unknown_skill_raises_key_error(tmp_path):
    reg = _reg(tmp_path)
    with pytest.raises(KeyError, match="demo"):
        asyncio.run(reg.load("demo"))


def test_build_skills_discovery(tmp_path):
    reg = _reg(tmp_path)
    store = AdminStore(str(tmp_path / "skills.db"))
    asyncio.run(store.connect())
    asyncio.run(store.create_skill("demo", "Demo skill", "body"))
    asyncio.run(store.close())
    assert asyncio.run(build_skills_discovery()) == "demo: Demo skill"


def test_parse_frontmatter_handles_malformed():
    assert parse_frontmatter("no frontmatter") == {}
    assert parse_frontmatter("---\nname: x\n---\nbody") == {"name": "x"}
    assert parse_frontmatter("---\n{{{\n---\nbody") == {}
