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
