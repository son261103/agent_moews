import asyncio

import pytest
from fastapi.testclient import TestClient

from src.api.chat_store import ChatStore


@pytest.fixture
def store(tmp_path):
    s = ChatStore(str(tmp_path / "chat.db"))
    asyncio.run(s.connect())
    yield s
    asyncio.run(s.close())


def test_store_roundtrip(store):
    asyncio.run(store.add_message("t1", "user", "xin chào", "2026-08-12T10:00:00.000001+00:00"))
    asyncio.run(store.add_message("t1", "assistant", "chào bạn", "2026-08-12T10:00:00.000002+00:00"))

    detail = asyncio.run(store.get_thread("t1"))
    assert detail is not None
    assert [m.role for m in detail.messages] == ["user", "assistant"]
    assert detail.messages[0].content == "xin chào"

    threads = asyncio.run(store.list_threads())
    assert len(threads) == 1
    assert threads[0].thread_id == "t1"
    assert threads[0].last_message == "chào bạn"


def test_store_empty_and_missing(store):
    assert asyncio.run(store.list_threads()) == []
    assert asyncio.run(store.get_thread("missing")) is None


def test_store_delete_thread(store):
    asyncio.run(store.add_message("t2", "user", "hi", "2026-08-12T10:00:00.000001+00:00"))
    asyncio.run(store.delete_thread("t2"))
    assert asyncio.run(store.get_thread("t2")) is None


def test_threads_api_list_get_delete(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)
    with TestClient(app) as client:
        asyncio.run(
            app.state.chat_store.add_message(
                "t-api", "user", "hello", "2026-08-12T10:00:00.000001+00:00"
            )
        )
        asyncio.run(
            app.state.chat_store.add_message(
                "t-api", "assistant", "hi there", "2026-08-12T10:00:00.000002+00:00"
            )
        )

        assert client.get("/api/v1/threads/nope").status_code == 404

        threads = client.get("/api/v1/threads").json()
        assert [t["thread_id"] for t in threads] == ["t-api"]
        assert threads[0]["last_message"] == "hi there"

        detail = client.get("/api/v1/threads/t-api").json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]

        assert client.delete("/api/v1/threads/t-api").status_code == 200
        assert client.get("/api/v1/threads/t-api").status_code == 404
