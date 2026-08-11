from src.config.settings import Settings
from src.llm.factory import create_llm

_ENV_VARS = [
    "OPENAI_API_KEY",
    "DEFAULT_MODEL",
    "FAST_MODEL",
    "LLM_BASE_URL",
]


def _isolated_settings(monkeypatch, **kwargs):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return Settings(_env_file=None, **kwargs)


def test_create_llm_uses_settings_model(monkeypatch):
    llm = create_llm(
        _isolated_settings(
            monkeypatch,
            openai_api_key="sk-test",
            tavily_api_key="tvly-test",
            default_model="gpt-4o",
        )
    )
    assert llm.model_name == "gpt-4o"
    assert llm.openai_api_base is None


def test_create_llm_uses_base_url_from_settings():
    llm = create_llm(
        Settings(
            openai_api_key="sk-test",
            tavily_api_key="tvly-test",
            llm_base_url="https://gateway.example/v1",
            _env_file=None,
        )
    )
    assert llm.openai_api_base == "https://gateway.example/v1"
