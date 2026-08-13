from src.skills.registry import get_skill_registry
from src.skills.tools import list_skills, load_skill


def test_list_skills_formats(tmp_path, monkeypatch):
    d = tmp_path / "demo"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Demo", encoding="utf-8"
    )
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert list_skills.invoke({}) == "demo: Demo skill"
    finally:
        get_skill_registry.cache_clear()


def test_load_skill_returns_content(tmp_path, monkeypatch):
    d = tmp_path / "demo"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Steps\n1. Do X", encoding="utf-8"
    )
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert load_skill.invoke({"name": "demo"}) == "# Steps\n1. Do X"
    finally:
        get_skill_registry.cache_clear()


def test_load_unknown_skill_returns_error_string(tmp_path, monkeypatch):
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert load_skill.invoke({"name": "nope"}) == "Skill not found: nope"
    finally:
        get_skill_registry.cache_clear()
