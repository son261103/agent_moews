from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, threads
from src.config.settings import Settings
from src.observability.langsmith import setup_langsmith


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Agent Moew API")

    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    setup_langsmith(settings)

    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(threads.router, prefix="/api/v1")

    return app
