import os

from src.config.settings import Settings


def setup_langsmith(settings: Settings) -> None:
    """Initialize LangSmith tracing via env vars. Call once at app startup."""
    if not settings.langsmith_tracing:
        return
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
