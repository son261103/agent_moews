import pytest
from fastapi.testclient import TestClient


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
    return TestClient(app)


def test_chat_stream_endpoint_exists(client):
    response = client.post("/chat/stream", json={"thread_id": "t1", "message": "hi"})
    assert response.status_code != 404
