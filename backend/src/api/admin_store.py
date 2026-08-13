"""SQLite-backed persistence for skills and OpenAPI configuration."""

from dataclasses import dataclass

import aiosqlite

from src.skills.registry import SkillInfo

DEFAULT_SKILL = (
    "code-review",
    "Review code systematically for correctness, security, and maintainability before reporting findings.",
    "# Code Review Skill\n\n"
    "Follow these steps when the user asks for a code review:\n\n"
    "1. Read the file(s) under review.\n"
    "2. Check for: correctness bugs, security issues (injection, secrets, auth), "
    "maintainability (dead code, unclear names).\n"
    "3. List findings as `[severity] file:line — issue` (severity: HIGH/MED/LOW).\n"
    "4. For each HIGH finding, propose a concrete fix.\n"
    "5. End with an overall verdict (Approved / Needs changes).",
)


@dataclass
class OpenApiConfig:
    spec_content: str = ""
    base_url: str = ""
    token: str = ""
    enabled: bool = False
    updated_at: str = ""


class AdminStore:
    """Persist skills and OpenAPI config in SQLite (same pattern as ChatStore)."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS openapi_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                spec_content TEXT NOT NULL DEFAULT '',
                base_url TEXT NOT NULL DEFAULT '',
                token TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def seed_default_skill(self) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute("SELECT COUNT(*) FROM skills")
        (count,) = await cursor.fetchone()
        await cursor.close()
        if count == 0:
            name, description, content = DEFAULT_SKILL
            await self._conn.execute(
                "INSERT INTO skills (name, description, content) VALUES (?, ?, ?)",
                (name, description, content),
            )
            await self._conn.commit()

    async def list_skills(self) -> list[SkillInfo]:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "SELECT name, description, content FROM skills ORDER BY name"
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            SkillInfo(name=r[0], description=r[1], path=None, content=r[2])
            for r in rows
        ]

    async def get_skill(self, name: str) -> SkillInfo | None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "SELECT name, description, content FROM skills WHERE name = ?", (name,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return SkillInfo(name=row[0], description=row[1], path=None, content=row[2])

    async def create_skill(self, name: str, description: str, content: str) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        try:
            await self._conn.execute(
                "INSERT INTO skills (name, description, content) VALUES (?, ?, ?)",
                (name, description, content),
            )
            await self._conn.commit()
        except aiosqlite.IntegrityError as exc:
            raise ValueError(f"Skill already exists: {name}") from exc

    async def update_skill(self, name: str, description: str, content: str) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "UPDATE skills SET description = ?, content = ?, "
            "updated_at = datetime('now') WHERE name = ?",
            (description, content, name),
        )
        await self._conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Skill not found: {name}")

    async def delete_skill(self, name: str) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "DELETE FROM skills WHERE name = ?", (name,)
        )
        await self._conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"Skill not found: {name}")

    async def get_openapi_config(self) -> OpenApiConfig:
        assert self._conn is not None, "AdminStore is not connected"
        cursor = await self._conn.execute(
            "SELECT spec_content, base_url, token, enabled, updated_at "
            "FROM openapi_config WHERE id = 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return OpenApiConfig()
        return OpenApiConfig(
            spec_content=row[0],
            base_url=row[1],
            token=row[2],
            enabled=bool(row[3]),
            updated_at=row[4],
        )

    async def save_openapi_config(
        self, spec_content: str, base_url: str, token: str, enabled: bool
    ) -> None:
        assert self._conn is not None, "AdminStore is not connected"
        await self._conn.execute(
            """
            INSERT INTO openapi_config (id, spec_content, base_url, token, enabled, updated_at)
            VALUES (1, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                spec_content = excluded.spec_content,
                base_url = excluded.base_url,
                token = excluded.token,
                enabled = excluded.enabled,
                updated_at = datetime('now')
            """,
            (spec_content, base_url, token, int(enabled)),
        )
        await self._conn.commit()
