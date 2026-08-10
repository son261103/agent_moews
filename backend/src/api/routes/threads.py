from fastapi import APIRouter

from src.api.schemas import ThreadDetail, ThreadInfo

router = APIRouter()


@router.get("/threads")
async def list_threads() -> list[ThreadInfo]:
    """List all conversation threads."""
    return []


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str) -> ThreadDetail:
    """Get a specific thread with all messages."""
    return ThreadDetail(thread_id=thread_id, messages=[])


@router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a conversation thread."""
    return {"status": "deleted"}
