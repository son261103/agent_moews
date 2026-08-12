"""SQLite-backed persistence for chat threads and messages."""

import aiosqlite

from src.api.schemas import ThreadDetail, ThreadInfo, ThreadMessage


class ChatStore:
    """Persist chat messages in SQLite. One row per message."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, timestamp)"
        )
        await self._conn.commit()

    async def add_message(
        self, thread_id: str, role: str, content: str, timestamp: str
    ) -> None:
        assert self._conn is not None, "ChatStore is not connected"
        await self._conn.execute(
            "INSERT INTO messages (thread_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (thread_id, role, content, timestamp),
        )
        await self._conn.commit()

    async def list_threads(self) -> list[ThreadInfo]:
        assert self._conn is not None, "ChatStore is not connected"
        cursor = await self._conn.execute(
            """
            SELECT m1.thread_id,
                   MIN(m1.timestamp) AS created_at,
                   (SELECT m2.content FROM messages m2
                     WHERE m2.thread_id = m1.thread_id
                     ORDER BY m2.timestamp DESC LIMIT 1) AS last_message
            FROM messages m1
            GROUP BY m1.thread_id
            ORDER BY MAX(m1.timestamp) DESC
            """
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            ThreadInfo(thread_id=r[0], created_at=r[1], last_message=r[2] or "")
            for r in rows
        ]

    async def get_thread(self, thread_id: str) -> ThreadDetail | None:
        assert self._conn is not None, "ChatStore is not connected"
        cursor = await self._conn.execute(
            "SELECT role, content, timestamp FROM messages "
            "WHERE thread_id = ? ORDER BY timestamp ASC",
            (thread_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        if not rows:
            return None
        return ThreadDetail(
            thread_id=thread_id,
            messages=[
                ThreadMessage(role=r[0], content=r[1], timestamp=r[2]) for r in rows
            ],
        )

    async def delete_thread(self, thread_id: str) -> None:
        assert self._conn is not None, "ChatStore is not connected"
        await self._conn.execute(
            "DELETE FROM messages WHERE thread_id = ?", (thread_id,)
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
