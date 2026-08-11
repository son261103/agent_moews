def test_create_app_returns_fastapi(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)
    assert app is not None
    assert hasattr(app, "routes")


def test_main_module_exposes_app():
    from fastapi import FastAPI

    from src.api.main import app

    assert isinstance(app, FastAPI)
