from src.config.settings import Settings
from src.llm.factory import create_llm


def test_create_llm_uses_default_settings():
    llm = create_llm(Settings(openai_api_key="sk-test", tavily_api_key="tvly-test"))
    assert llm.model_name == "gpt-4o"
    assert llm.openai_api_base is None


def test_create_llm_uses_base_url_from_settings():
    llm = create_llm(
        Settings(
            openai_api_key="sk-test",
            tavily_api_key="tvly-test",
            llm_base_url="https://gateway.example/v1",
        )
    )
    assert llm.openai_api_base == "https://gateway.example/v1"
