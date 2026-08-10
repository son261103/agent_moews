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
