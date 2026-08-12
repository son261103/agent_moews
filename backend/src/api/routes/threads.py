from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import ThreadDetail, ThreadInfo

router = APIRouter()


@router.get("/threads")
async def list_threads(http_request: Request) -> list[ThreadInfo]:
    """List all conversation threads, newest first."""
    store = http_request.app.state.chat_store
    return await store.list_threads()


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str, http_request: Request) -> ThreadDetail:
    """Get a specific thread with all messages."""
    store = http_request.app.state.chat_store
    thread = await store.get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, http_request: Request):
    """Delete a conversation thread."""
    store = http_request.app.state.chat_store
    await store.delete_thread(thread_id)
    return {"status": "deleted"}
