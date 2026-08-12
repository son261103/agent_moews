import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from src.api.schemas import ChatRequest

router = APIRouter()


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    """Stream agent responses via Server-Sent Events."""
    graph = http_request.app.state.graph

    config = {"configurable": {"thread_id": request.thread_id}}
    input_state = {"messages": [("user", request.message)], "reflection_round": 0}

    async def event_generator():
        root_run_id = None
        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name == "LangGraph" and root_run_id is None:
                    root_run_id = event.get("run_id")

                if kind == "on_chain_start" and name == "deep_agent":
                    yield json.dumps({"type": "reset"})

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", "")
                    if hasattr(chunk, "content"):
                        chunk_data = chunk.content
                    else:
                        chunk_data = str(chunk)
                    if not chunk_data:
                        continue
                    yield json.dumps({"type": "token", "content": chunk_data})

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
                    yield json.dumps({"type": "done"})

        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)})

    return EventSourceResponse(event_generator())
