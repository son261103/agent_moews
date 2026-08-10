from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str
    message: str


class ThreadInfo(BaseModel):
    thread_id: str
    created_at: str
    last_message: str


class ThreadMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ThreadDetail(BaseModel):
    thread_id: str
    messages: list[ThreadMessage]
