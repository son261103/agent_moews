import os

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore

from src.config.settings import Settings


async def get_checkpointer(settings: Settings) -> AsyncSqliteSaver:
    """SQLite-backed checkpointer for thread persistence."""
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(settings.db_path)
    return AsyncSqliteSaver(conn)


async def get_memory_store(settings: Settings) -> InMemoryStore:
    """InMemory store placeholder. Replace with SQLiteStore for persistence."""
    return InMemoryStore()
