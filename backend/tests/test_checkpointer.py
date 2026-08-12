import asyncio
import gc

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
    await cp.conn.close()


@pytest.mark.asyncio
async def test_checkpointer_survives_gc(tmp_path):
    from src.config.settings import Settings
    from src.graph.checkpointer import get_checkpointer

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    cp = await get_checkpointer(test_settings)

    gc.collect()
    await asyncio.sleep(0.05)
    gc.collect()
    await asyncio.sleep(0.05)

    result = await cp.aget_tuple({"configurable": {"thread_id": "t1", "checkpoint_ns": ""}})
    assert result is None
    await cp.conn.close()
