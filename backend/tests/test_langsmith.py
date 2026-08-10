import os


def test_setup_langsmith_sets_env_vars(monkeypatch):
    from src.config.settings import Settings
    from src.observability.langsmith import setup_langsmith

    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        langsmith_tracing=True,
        langsmith_project="agent-moew",
        langsmith_endpoint="https://api.smith.langchain.com",
    )
    result = setup_langsmith(test_settings)

    assert result is None
    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_ENDPOINT") == "https://api.smith.langchain.com"
    assert os.environ.get("LANGSMITH_API_KEY") == "ls-test"
    assert os.environ.get("LANGSMITH_PROJECT") == "agent-moew"


def test_setup_langsmith_noop_when_disabled(monkeypatch):
    from src.config.settings import Settings
    from src.observability.langsmith import setup_langsmith

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "should-stay")

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        langsmith_tracing=False,
    )
    result = setup_langsmith(test_settings)

    assert result is None
    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_API_KEY") == "should-stay"


def test_setup_langsmith_noop_without_api_key(monkeypatch):
    from src.config.settings import Settings
    from src.observability.langsmith import setup_langsmith

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "should-stay")

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key=None,
    )
    result = setup_langsmith(test_settings)

    assert result is None
    assert os.environ.get("LANGSMITH_TRACING") == "true"
    assert os.environ.get("LANGSMITH_API_KEY") == "should-stay"
