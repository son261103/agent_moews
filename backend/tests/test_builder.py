import pytest


@pytest.mark.asyncio
async def test_build_graph_returns_runnable(tmp_path):
    from src.config.settings import Settings
    from src.graph.builder import build_graph

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    graph = await build_graph(test_settings)
    assert graph is not None
    assert hasattr(graph, "astream_events")
    await graph.checkpointer.conn.close()


@pytest.mark.asyncio
async def test_build_graph_uses_supervisor_tools(tmp_path):
    from unittest.mock import patch

    from langchain_core.tools import tool

    from src.config.settings import Settings
    from src.graph.builder import build_graph

    @tool
    def fake_research_tool(query: str) -> str:
        """Fake research."""
        return ""

    @tool
    def fake_info_tool(query: str) -> str:
        """Fake info."""
        return ""

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    fake_tools = [fake_research_tool, fake_info_tool]
    with patch(
        "src.graph.builder.build_supervisor_tools", return_value=fake_tools
    ) as mock_build:
        graph = await build_graph(test_settings)

    mock_build.assert_called_once()
    assert graph is not None
    await graph.checkpointer.conn.close()


def test_build_graph_includes_skill_tools(tmp_path, monkeypatch):
    from src.skills.registry import get_skill_registry
    from src.skills.tools import list_skills, load_skill
    from src.tools.registry import get_all_tools

    d = tmp_path / "demo"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Demo", encoding="utf-8"
    )
    monkeypatch.setattr("src.skills.registry.settings.skills_dir", str(tmp_path))
    get_skill_registry.cache_clear()
    try:
        names = {t.name for t in get_all_tools()}
        assert "load_skill" in names and "list_skills" in names
    finally:
        get_skill_registry.cache_clear()
