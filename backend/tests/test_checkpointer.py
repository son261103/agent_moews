import pytest


@pytest.mark.asyncio
async def test_get_checkpointer_sqlite(tmp_path):
    from src.config.settings import Settings
    from src.graph.checkpointer import get_checkpointer

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    cp = await get_checkpointer(test_settings)
    assert cp is not None
