from langchain_openai import ChatOpenAI

from src.config.settings import Settings


def create_llm(settings: Settings) -> ChatOpenAI:
    """Create a ChatOpenAI instance from settings."""
    return ChatOpenAI(
        model=settings.default_model,
        api_key=settings.openai_api_key,
    )
