from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.chat_store import ChatStore
from src.api.routes import chat, threads
from src.config.settings import Settings, settings
from src.graph.builder import build_graph
from src.observability.langsmith import setup_langsmith


@asynccontextmanager
async def lifespan(app: FastAPI):
    graph = await build_graph(app.state.settings)
    app.state.graph = graph
    chat_store = ChatStore(app.state.settings.db_path)
    await chat_store.connect()
    app.state.chat_store = chat_store
    try:
        yield
    finally:
        await chat_store.close()
        checkpointer = getattr(graph, "checkpointer", None)
        conn = getattr(checkpointer, "conn", None)
        if conn is not None:
            await conn.close()


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Agent Moew API", lifespan=lifespan)

    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    setup_langsmith(settings)

    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(threads.router, prefix="/api/v1")

    return app


app = create_app(settings)
