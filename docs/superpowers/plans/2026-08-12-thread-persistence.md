# Thread Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist chat threads and messages in SQLite so reloading the page keeps history, the sidebar lists real conversations, and stream failures show visible errors instead of silently hanging.

**Architecture:** A small async SQLite-backed `ChatStore` (using `aiosqlite`, already a dependency via `langgraph-checkpoint-sqlite`) stores one row per message. The chat stream endpoint saves the user message at request start and the assistant reply when the stream finishes (or the error text on failure). The `/threads` endpoints read from the store. The frontend loads history via the existing-but-unused `getThread()` on thread mount, passes an `onError` callback to `streamChat` (currently the error is swallowed silently), and refreshes the sidebar list after each turn.

**Tech Stack:** Python 3.12, FastAPI, aiosqlite 0.21 (existing), Next.js 16 + React 19 + SWR (already used).

## Global Constraints

- **No new dependencies** — aiosqlite is already installed; stdlib only otherwise.
- **Vietnamese user-facing strings** — all messages shown to users (frontend and tool outputs) in Vietnamese.
- **SSE contract unchanged** — event types/fields emitted by `/chat/stream` must stay identical (reset/token/tool_start/tool_end/reflection/plan/done/error).
- **Existing backend tests stay green** — the current 40 tests must all pass after each task.
- **Existing tests must keep passing without mocking the store** — tests use `TestClient` with `tmp_path` db via `Settings(db_path=...)`; the store must work against a fresh temp db (no ambient env, no network).
- **Commit per task** with a short conventional message.
- `data/` and `*.db` are already gitignored (verified: `.gitignore` lines 29-32) — no `.gitignore` changes needed.

---

### Task 1: SQLite ChatStore + threads endpoints

**Files:**
- Create: `backend/src/chat_store.py`
- Modify: `backend/src/api/routes/threads.py` (full rewrite, 31 lines)
- Modify: `backend/src/api/main.py:12-22` (lifespan wiring)
- Test: `backend/tests/test_threads.py` (full rewrite)

**Interfaces:**
- Consumes: `src.api.schemas.ThreadInfo`, `ThreadDetail`, `ThreadMessage` (all exist in `backend/src/api/schemas.py`, unchanged).
- Produces: `ChatStore` class with async methods `connect()`, `add_message(thread_id, role, content, timestamp)`, `list_threads() -> list[ThreadInfo]`, `get_thread(thread_id) -> ThreadDetail | None`, `delete_thread(thread_id)`, `close()`. Task 2 uses `app.state.chat_store` (set in lifespan, same pattern as `app.state.graph`).

- [ ] **Step 1: Write the failing tests** — replace `backend/tests/test_threads.py` entirely with:

```python
import asyncio

import pytest
from fastapi.testclient import TestClient

from src.api.chat_store import ChatStore


@pytest.fixture
def store(tmp_path):
    s = ChatStore(str(tmp_path / "chat.db"))
    asyncio.run(s.connect())
    yield s
    asyncio.run(s.close())


def test_store_roundtrip(store):
    asyncio.run(store.add_message("t1", "user", "xin chào", "2026-08-12T10:00:00.000001+00:00"))
    asyncio.run(store.add_message("t1", "assistant", "chào bạn", "2026-08-12T10:00:00.000002+00:00"))

    detail = asyncio.run(store.get_thread("t1"))
    assert detail is not None
    assert [m.role for m in detail.messages] == ["user", "assistant"]
    assert detail.messages[0].content == "xin chào"

    threads = asyncio.run(store.list_threads())
    assert len(threads) == 1
    assert threads[0].thread_id == "t1"
    assert threads[0].last_message == "chào bạn"


def test_store_empty_and_missing(store):
    assert asyncio.run(store.list_threads()) == []
    assert asyncio.run(store.get_thread("missing")) is None


def test_store_delete_thread(store):
    asyncio.run(store.add_message("t2", "user", "hi", "2026-08-12T10:00:00.000001+00:00"))
    asyncio.run(store.delete_thread("t2"))
    assert asyncio.run(store.get_thread("t2")) is None


def test_threads_api_list_get_delete(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)
    with TestClient(app) as client:
        asyncio.run(
            app.state.chat_store.add_message(
                "t-api", "user", "hello", "2026-08-12T10:00:00.000001+00:00"
            )
        )
        asyncio.run(
            app.state.chat_store.add_message(
                "t-api", "assistant", "hi there", "2026-08-12T10:00:00.000002+00:00"
            )
        )

        assert client.get("/api/v1/threads/nope").status_code == 404

        threads = client.get("/api/v1/threads").json()
        assert [t["thread_id"] for t in threads] == ["t-api"]
        assert threads[0]["last_message"] == "hi there"

        detail = client.get("/api/v1/threads/t-api").json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]

        assert client.delete("/api/v1/threads/t-api").status_code == 200
        assert client.get("/api/v1/threads/t-api").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_threads.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.chat_store'` (and `test_threads_api_list_get_delete` fails because `app.state.chat_store` is not set).

- [ ] **Step 3: Create `backend/src/chat_store.py`**

```python
"""SQLite-backed persistence for chat threads and messages."""

import aiosqlite

from src.api.schemas import ThreadDetail, ThreadInfo, ThreadMessage


class ChatStore:
    """Persist chat messages in SQLite. One row per message."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, timestamp)"
        )
        await self._conn.commit()

    async def add_message(
        self, thread_id: str, role: str, content: str, timestamp: str
    ) -> None:
        assert self._conn is not None, "ChatStore is not connected"
        await self._conn.execute(
            "INSERT INTO messages (thread_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (thread_id, role, content, timestamp),
        )
        await self._conn.commit()

    async def list_threads(self) -> list[ThreadInfo]:
        assert self._conn is not None, "ChatStore is not connected"
        cursor = await self._conn.execute(
            """
            SELECT m1.thread_id,
                   MIN(m1.timestamp) AS created_at,
                   (SELECT m2.content FROM messages m2
                     WHERE m2.thread_id = m1.thread_id
                     ORDER BY m2.timestamp DESC LIMIT 1) AS last_message
            FROM messages m1
            GROUP BY m1.thread_id
            ORDER BY MAX(m1.timestamp) DESC
            """
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            ThreadInfo(thread_id=r[0], created_at=r[1], last_message=r[2] or "")
            for r in rows
        ]

    async def get_thread(self, thread_id: str) -> ThreadDetail | None:
        assert self._conn is not None, "ChatStore is not connected"
        cursor = await self._conn.execute(
            "SELECT role, content, timestamp FROM messages "
            "WHERE thread_id = ? ORDER BY timestamp ASC",
            (thread_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        if not rows:
            return None
        return ThreadDetail(
            thread_id=thread_id,
            messages=[
                ThreadMessage(role=r[0], content=r[1], timestamp=r[2]) for r in rows
            ],
        )

    async def delete_thread(self, thread_id: str) -> None:
        assert self._conn is not None, "ChatStore is not connected"
        await self._conn.execute(
            "DELETE FROM messages WHERE thread_id = ?", (thread_id,)
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
```

- [ ] **Step 4: Rewrite `backend/src/api/routes/threads.py`** (replace all 23 lines):

```python
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
```

- [ ] **Step 5: Wire the store into `backend/src/api/main.py` lifespan** (edit lines 12-22). The import goes at the top with the other imports:

```python
from src.api.chat_store import ChatStore
```

And the lifespan body becomes:

```python
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
```

- [ ] **Step 6: Run the full test suite**

Run: `uv run python -m pytest`
Expected: PASS — all 40 existing tests plus the 4 new ones (44 total). The suite must run green from `backend/` with `uv run python -m pytest`.

- [ ] **Step 7: Commit**

```bash
git add backend/src/chat_store.py backend/src/api/routes/threads.py backend/src/api/main.py backend/tests/test_threads.py
git commit -m "feat: persist chat threads in SQLite"
```

---

### Task 2: Save messages from the chat stream

**Files:**
- Modify: `backend/src/api/routes/chat.py`
- Test: `backend/tests/test_chat_stream.py` (append one test)

**Interfaces:**
- Consumes: `ChatStore` from Task 1 via `http_request.app.state.chat_store` (set in lifespan).
- Produces: nothing new — persistence only. The SSE event stream is unchanged.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_chat_stream.py` (after `test_chat_stream_emits_tool_names_and_single_done`, at end of file):

```python
def test_chat_stream_persists_messages(tmp_path):
    from src.api.main import create_app
    from src.config.settings import Settings
    import src.graph.builder as builder_mod

    builder_mod.create_llm = lambda settings: FakeToolLLM()

    test_settings = Settings(
        openai_api_key="sk-test",
        tavily_api_key="tvly-test",
        langsmith_api_key="ls-test",
        db_path=str(tmp_path / "test.db"),
    )
    app = create_app(test_settings)

    with TestClient(app) as client:
        with client.stream(
            "POST", "/api/v1/chat/stream",
            json={"thread_id": "t-persist", "message": "hello"},
        ) as resp:
            resp.read()

        detail = client.get("/api/v1/threads/t-persist").json()
        assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
        assert detail["messages"][0]["content"] == "hello"
        assert detail["messages"][1]["content"] == "Final answer text."
```

Note: `FakeToolLLM` (defined at the top of `test_chat_stream.py`, already in the file) makes turn 0 a `get_current_time` tool call with empty content and turn 1+ the text `"Final answer text."` — so the saved assistant message is exactly `"Final answer text."` (empty tool-call chunks emit no tokens).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_chat_stream.py::test_chat_stream_persists_messages -v`
Expected: FAIL — `detail["messages"]` is `[]` (nothing is saved yet).

- [ ] **Step 3: Modify `backend/src/api/routes/chat.py`**

Add imports at the top (after the existing `import json` / fastapi imports):

```python
from datetime import datetime, timezone
```

Inside `chat_stream`, before `async def event_generator():`, save the user message immediately (add after the `input_state = ...` line):

```python
    store = http_request.app.state.chat_store
    await store.add_message(
        request.thread_id,
        "user",
        request.message,
        datetime.now(timezone.utc).isoformat(),
    )
```

Inside `event_generator`, right after `root_run_id = None`:

```python
        assistant_parts: list[str] = []
```

In the `on_chat_model_stream` branch, after the line `yield json.dumps({"type": "token", "content": chunk_data})`, accumulate the chunk (the same `chunk_data` variable):

```python
                    assistant_parts.append(chunk_data)
```

In the `done` branch (the `elif` for `on_chain_end` / `LangGraph` / root run), before `yield json.dumps({"type": "done"})`, save the assistant reply:

```python
                    await store.add_message(
                        request.thread_id,
                        "assistant",
                        "".join(assistant_parts),
                        datetime.now(timezone.utc).isoformat(),
                    )
```

In the `except Exception as e:` branch, before `yield json.dumps({"type": "error", ...})`, also save the failure as the assistant message so the history shows what happened:

```python
            await store.add_message(
                request.thread_id,
                "assistant",
                f"Lỗi: {e}",
                datetime.now(timezone.utc).isoformat(),
            )
```

The resulting `event_generator` body must be:

```python
    async def event_generator():
        root_run_id = None
        assistant_parts: list[str] = []
        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name == "LangGraph" and root_run_id is None:
                    root_run_id = event.get("run_id")

                if kind == "on_chain_start" and name == "deep_agent":
                    yield json.dumps({"type": "reset"})

                if kind == "on_chain_start" and name == "reflect":
                    yield json.dumps({"type": "reflection", "status": "start"})

                if kind == "on_chain_end" and name == "reflect":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        feedback = output.get("feedback", "")
                    else:
                        feedback = str(output)
                    if len(str(feedback)) > 200:
                        feedback = str(feedback)[:200] + "..."
                    yield json.dumps({"type": "reflection", "status": "end", "content": str(feedback)})

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", "")
                    if hasattr(chunk, "content"):
                        chunk_data = chunk.content
                    else:
                        chunk_data = str(chunk)
                    if not chunk_data:
                        continue
                    yield json.dumps({"type": "token", "content": chunk_data})
                    assistant_parts.append(chunk_data)

                elif kind == "on_tool_start":
                    yield json.dumps({
                        "type": "tool_start",
                        "tool": name,
                    })

                elif kind == "on_tool_end":
                    output = event.get("data", {}).get("output", "")
                    if hasattr(output, "content"):
                        output = output.content
                    if len(str(output)) > 200:
                        output = str(output)[:200] + "..."
                    yield json.dumps({
                        "type": "tool_end",
                        "tool": name,
                        "output": str(output),
                    })

                elif (
                    kind == "on_chain_end"
                    and name == "LangGraph"
                    and root_run_id
                    and event.get("run_id") == root_run_id
                ):
                    await store.add_message(
                        request.thread_id,
                        "assistant",
                        "".join(assistant_parts),
                        datetime.now(timezone.utc).isoformat(),
                    )
                    yield json.dumps({"type": "done"})

        except Exception as e:
            await store.add_message(
                request.thread_id,
                "assistant",
                f"Lỗi: {e}",
                datetime.now(timezone.utc).isoformat(),
            )
            yield json.dumps({"type": "error", "message": str(e)})

    return EventSourceResponse(event_generator())
```

Do not change anything else in `chat.py` — the SSE event types and payloads stay byte-identical.

- [ ] **Step 4: Run the new test and full suite**

Run: `uv run python -m pytest`
Expected: PASS — 45 tests total (44 + the new persistence test). The existing `test_chat_stream_emits_tool_names_and_single_done` must still pass unchanged (it asserts exactly one `done` and the same token content).

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/chat.py backend/tests/test_chat_stream.py
git commit -m "feat: persist chat messages from stream"
```

---

### Task 3: Frontend — load history, surface errors, refresh sidebar

**Files:**
- Modify: `frontend/components/ChatWindow.tsx`
- Modify: `frontend/components/ThreadSidebar.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:**
- Consumes: `getThread(threadId)` and `ThreadMessage` from `frontend/lib/api.ts` (exists, currently unused); `streamChat`'s 4th `onError?: (error: Error) => void` parameter (exists in `frontend/lib/sse.ts:14`).
- Produces: `ChatWindow` accepts a new optional prop `onThreadUpdated?: () => void`, called after each completed turn (done/error) so the sidebar can refresh.

- [ ] **Step 1: Modify `frontend/components/ChatWindow.tsx`**

1a. Add the import after line 7 (`import { streamChat, StreamEvent } from "@/lib/sse";`):

```tsx
import { getThread } from "@/lib/api";
```

1b. Change the component signature (line 34) from:

```tsx
export default function ChatWindow({ threadId }: { threadId: string }) {
```

to:

```tsx
export default function ChatWindow({
  threadId,
  onThreadUpdated,
}: {
  threadId: string;
  onThreadUpdated?: () => void;
}) {
```

1c. Add a history-loading effect right after the existing "Cleanup on unmount" effect (after line 57):

```tsx
  // Load thread history on mount
  useEffect(() => {
    let cancelled = false;
    setMessages([]);
    setToolCalls([]);
    setStreamContent("");
    setThinking({ isRunning: false, content: "" });
    getThread(threadId).then((thread) => {
      if (cancelled || !thread) return;
      setMessages(
        thread.messages.map((m, i) => ({
          id: `${m.timestamp}-${i}`,
          content: m.content,
          isUser: m.role === "user",
        }))
      );
    });
    return () => {
      cancelled = true;
    };
  }, [threadId]);
```

1d. In the `done` case, after `setThinking((prev) => ({ ...prev, isRunning: false }));` (line 156), add:

```tsx
            onThreadUpdated?.();
```

1e. In the `error` case, after `setThinking((prev) => ({ ...prev, isRunning: false }));` (line 170), add:

```tsx
            onThreadUpdated?.();
```

1f. Pass the `onError` callback as the 4th argument of `streamChat` — after the event callback's closing `)` on line 173, before the final `);` of the `streamChat(...)` call, add:

```tsx
      ,
      (err) => {
        setIsLoading(false);
        setThinking({ isRunning: false, content: "" });
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            content: `Lỗi: ${err.message || "Không kết nối được máy chủ"}`,
            isUser: false,
          },
        ]);
      }
```

The call must read:

```tsx
    stopRef.current = streamChat(
      threadId,
      input.trim(),
      (event: StreamEvent) => {
        // ... existing switch, unchanged ...
      },
      (err) => {
        setIsLoading(false);
        setThinking({ isRunning: false, content: "" });
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            content: `Lỗi: ${err.message || "Không kết nối được máy chủ"}`,
            isUser: false,
          },
        ]);
      }
    );
```

1g. Update the `useCallback` dependency array (line 175) from `[input, isLoading, threadId]` to `[input, isLoading, threadId, onThreadUpdated]`.

- [ ] **Step 2: Modify `frontend/components/ThreadSidebar.tsx`**

Change the component signature (lines 11-19) from:

```tsx
export default function ThreadSidebar({
  currentThreadId,
  onSelectThread,
  onNewThread,
}: {
  currentThreadId: string;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
}) {
  const { data: threads } = useSWR("threads", listThreads);
```

to:

```tsx
export default function ThreadSidebar({
  currentThreadId,
  onSelectThread,
  onNewThread,
  refreshKey,
}: {
  currentThreadId: string;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
  refreshKey: number;
}) {
  const { data: threads } = useSWR(["threads", refreshKey], listThreads);
```

Nothing else in the file changes.

- [ ] **Step 3: Modify `frontend/app/page.tsx`** (replace the whole file, 22 lines):

```tsx
"use client";

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import ThreadSidebar from "@/components/ThreadSidebar";

export default function Home() {
  const [currentThreadId, setCurrentThreadId] = useState("default");
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="flex h-full">
      <ThreadSidebar
        currentThreadId={currentThreadId}
        onSelectThread={setCurrentThreadId}
        onNewThread={() => setCurrentThreadId(`thread-${Date.now()}`)}
        refreshKey={refreshKey}
      />
      <main className="flex-1 min-w-0">
        <ChatWindow
          key={currentThreadId}
          threadId={currentThreadId}
          onThreadUpdated={() => setRefreshKey((k) => k + 1)}
        />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Build the frontend**

Run: `npm run build`
Expected: `Compiled successfully` — no TypeScript errors, static pages generated.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ChatWindow.tsx frontend/components/ThreadSidebar.tsx frontend/app/page.tsx
git commit -m "feat: load chat history and surface stream errors"
```
