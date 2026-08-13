from pathlib import Path

import pytest

from src.skills.registry import SkillRegistry, build_skills_discovery


def _write_skill(root: Path, name: str, description: str, body: str = "# Steps\n1. Do it") -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}", encoding="utf-8"
    )


def test_scan_lists_skills_in_sorted_order(tmp_path):
    _write_skill(tmp_path, "beta", "B skill")
    _write_skill(tmp_path, "alpha", "A skill")
    reg = SkillRegistry(tmp_path)
    names = [s.name for s in reg.list_skills()]
    assert names == ["alpha", "beta"]


def test_scan_skips_missing_description(tmp_path):
    d = tmp_path / "no-desc"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: no-desc\n---\nbody", encoding="utf-8")
    reg = SkillRegistry(tmp_path)
    assert reg.list_skills() == []


def test_load_returns_body_without_frontmatter(tmp_path):
    _write_skill(tmp_path, "demo", "Demo skill", "# Demo\nSteps here")
    reg = SkillRegistry(tmp_path)
    content = reg.load("demo")
    assert content == "# Demo\nSteps here"
    assert "name:" not in content


def test_load_unknown_skill_raises_key_error(tmp_path):
    reg = SkillRegistry(tmp_path)
    with pytest.raises(KeyError, match="demo"):
        reg.load("demo")


def test_build_skills_discovery(tmp_path, monkeypatch):
    from src.skills.registry import get_skill_registry

    _write_skill(tmp_path, "demo", "Demo skill")
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        assert build_skills_discovery() == "demo: Demo skill"
    finally:
        get_skill_registry.cache_clear()
