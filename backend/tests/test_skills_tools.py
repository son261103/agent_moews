import asyncio

from src.skills.tools import list_skills, load_skill


def _seed(tmp_path, name="demo", description="Demo skill", content="# Demo"):
    import src.config.settings as settings_module
    from src.api.admin_store import AdminStore
    from src.skills.registry import get_skill_registry

    settings_module.settings.db_path = str(tmp_path / "skills.db")
    get_skill_registry.cache_clear()
    store = AdminStore(str(tmp_path / "skills.db"))
    asyncio.run(store.connect())
    asyncio.run(store.create_skill(name, description, content))
    asyncio.run(store.close())


def test_list_skills_formats(tmp_path):
    _seed(tmp_path)
    assert asyncio.run(list_skills.ainvoke({})) == "demo: Demo skill"


def test_load_skill_returns_content(tmp_path):
    _seed(tmp_path, content="# Steps\n1. Do X")
    assert asyncio.run(load_skill.ainvoke({"name": "demo"})) == "# Steps\n1. Do X"


def test_load_unknown_skill_returns_error_string(tmp_path):
    assert asyncio.run(load_skill.ainvoke({"name": "nope"})) == "Skill not found: nope"
