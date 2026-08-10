from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    # Required in production (loaded from .env); Optional here so tests can
    # construct Settings without ambient env, and the module can be imported
    # without raising at import time.
    openai_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    langsmith_api_key: Optional[str] = None

    # LangSmith
    langsmith_tracing: bool = True
    langsmith_project: str = "agent-moew"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # Models
    default_model: str = "gpt-4o"
    fast_model: str = "gpt-4o-mini"
    llm_base_url: Optional[str] = None

    # Paths
    db_path: str = "data/agent_moew.db"
    workspace_dir: str = "workspace"


settings = Settings()
