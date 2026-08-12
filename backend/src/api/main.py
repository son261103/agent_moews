from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, threads
from src.config.settings import Settings, settings
from src.graph.builder import build_graph
from src.observability.langsmith import setup_langsmith


@asynccontextmanager
async def lifespan(app: FastAPI):
    graph = await build_graph(app.state.settings)
    app.state.graph = graph
    try:
        yield
    finally:
        checkpointer = getattr(graph, "checkpointer", None)
        conn = getattr(checkpointer, "conn", None)
        if conn is not None:
            await conn.close()


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Agent Moew API", lifespan=lifespan)

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


app = create_app(settings)
