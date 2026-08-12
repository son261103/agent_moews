import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class FakeToolLLM(BaseChatModel):
    """Turn 0 -> tool call to get_current_time, turn 1+ -> final answer."""

    _n: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        return self

    def _response(self, n: int) -> AIMessage:
        if n == 0:
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "get_current_time", "args": {}, "id": "call_1"}
                ],
            )
        return AIMessage(content="Final answer text.")

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        n = self._n
        self._n += 1
        return ChatResult(generations=[ChatGeneration(message=self._response(n))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        n = self._n
        self._n += 1
        msg = self._response(n)
        if msg.tool_calls:
            chunks = [
                {
                    "name": tc["name"],
                    "args": json.dumps(tc["args"]),
                    "id": tc["id"],
                    "index": i,
                }
                for i, tc in enumerate(msg.tool_calls)
            ]
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="", tool_call_chunks=chunks)
            )
        else:
            yield ChatGenerationChunk(message=AIMessageChunk(content=msg.content))


@pytest.fixture
def client(tmp_path):
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
        yield client


def test_chat_stream_endpoint_exists(client):
    response = client.post("/api/v1/chat/stream", json={"thread_id": "t1", "message": "hi"})
    assert response.status_code != 404


def test_chat_stream_emits_tool_names_and_single_done(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings
    import src.graph.builder as builder_mod

    builder_mod.create_llm = lambda settings: FakeToolLLM()

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)

    events = []
    with TestClient(app) as client:
        with client.stream(
            "POST", "/api/v1/chat/stream",
            json={"thread_id": "t1", "message": "hello"},
        ) as resp:
            for line in resp.iter_lines():
                if line.startswith("data:") and line.strip() != "data:":
                    events.append(json.loads(line[5:].strip()))

    tool_starts = [e for e in events if e["type"] == "tool_start"]
    dones = [e for e in events if e["type"] == "done"]
    tokens = [e for e in events if e["type"] == "token"]

    assert tool_starts, "expected at least one tool_start event"
    assert all(e["tool"] for e in tool_starts), "tool name must not be empty"
    assert any(e["tool"] == "get_current_time" for e in tool_starts)
    assert len(dones) == 1, f"expected exactly one done, got {len(dones)}"
    assert any("Final answer text." in e["content"] for e in tokens)


def test_chat_stream_persists_messages(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings
    import src.graph.builder as builder_mod

    builder_mod.create_llm = lambda settings: FakeToolLLM()

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)

    with TestClient(app) as client:
        events = []
        with client.stream(
            "POST", "/api/v1/chat/stream",
            json={"thread_id": "t-persist", "message": "hello"},
        ) as resp:
            for line in resp.iter_lines():
                if line.startswith("data:") and line.strip() != "data:":
                    events.append(json.loads(line[5:].strip()))

        # The graph streams model output from deep_agent, the sub-agent and
        # reflect (FakeToolLLM returns the same text for each call), so the
        # reply is the concatenation of every streamed token.
        streamed = "".join(e.get("content", "") for e in events if e["type"] == "token")
        assert streamed, "expected streamed tokens"

        detail = client.get("/api/v1/threads/t-persist").json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][0]["content"] == "hello"
        assert detail["messages"][1]["content"] == streamed
