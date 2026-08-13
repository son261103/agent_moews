def test_settings_loads_env():
    from src.config.settings import Settings
    s = Settings(
        openai_api_key="sk-test-key",
        tavily_api_key="tvly-test-key",
        langsmith_api_key="ls-test-key",
    )
    assert s.openai_api_key == "sk-test-key"
    assert s.tavily_api_key == "tvly-test-key"


_ALL_SETTING_ENV_VARS = [
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
    "LANGSMITH_API_KEY",
    "LANGSMITH_TRACING",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
    "DEFAULT_MODEL",
    "FAST_MODEL",
    "LLM_BASE_URL",
    "DB_PATH",
    "WORKSPACE_DIR",
]


def _isolated_settings(monkeypatch, **kwargs):
    from src.config.settings import Settings
    for var in _ALL_SETTING_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return Settings(_env_file=None, **kwargs)


def test_settings_has_defaults(monkeypatch):
    s = _isolated_settings(
        monkeypatch,
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
    )
    assert s.default_model
    assert s.fast_model
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


def test_openapi_and_skills_settings_defaults():
    from src.config.settings import Settings
    s = Settings()
    assert s.openapi_spec_path is None
    assert s.openapi_base_url is None
    assert s.openapi_token is None
    assert s.skills_dir == "skills"
