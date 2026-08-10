def test_settings_loads_env():
    from src.config.settings import Settings
    s = Settings(
        openai_api_key="sk-test-key",
        tavily_api_key="tvly-test-key",
        langsmith_api_key="ls-test-key",
    )
    assert s.openai_api_key == "sk-test-key"
    assert s.tavily_api_key == "tvly-test-key"


def test_settings_has_defaults():
    from src.config.settings import Settings
    s = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
    )
    assert s.default_model == "gpt-4o"
    assert s.fast_model == "gpt-4o-mini"
    assert s.llm_base_url is None
    assert s.langsmith_tracing is True
    assert s.langsmith_project == "agent-moew"
    assert s.langsmith_endpoint == "https://api.smith.langchain.com"


def test_settings_reads_llm_base_url_from_env(monkeypatch):
    from src.config.settings import Settings
    monkeypatch.setenv("LLM_BASE_URL", "https://gateway.example/v1")
    s = Settings(openai_api_key="sk-test", tavily_api_key="tvly-test")
    assert s.llm_base_url == "https://gateway.example/v1"


def test_settings_reads_langsmith_endpoint_from_env(monkeypatch):
    from src.config.settings import Settings
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://eu.smith.langchain.com")
    s = Settings(openai_api_key="sk-test", tavily_api_key="tvly-test")
    assert s.langsmith_endpoint == "https://eu.smith.langchain.com"
