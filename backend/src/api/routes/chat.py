import json
from datetime import datetime, timezone

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

    store = http_request.app.state.chat_store
    await store.add_message(
        request.thread_id,
        "user",
        request.message,
        datetime.now(timezone.utc).isoformat(),
    )

    async def event_generator():
        root_run_id = None
        assistant_parts: list[str] = []
        tool_calls_executed: list[dict] = []
        thinking_data: dict = {"isRunning": False, "content": ""}
        try:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name == "LangGraph" and root_run_id is None:
                    root_run_id = event.get("run_id")

                if kind == "on_chain_start" and name == "reflect":
                    thinking_data["isRunning"] = True
                    yield json.dumps({"type": "reflection", "status": "start"})

                if kind == "on_chain_end" and name == "reflect":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        feedback = output.get("feedback", "")
                    else:
                        feedback = str(output)
                    if len(str(feedback)) > 4000:
                        feedback = str(feedback)[:4000] + "..."
                    thinking_data["isRunning"] = False
                    thinking_data["content"] = str(feedback)
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
                    run_id = event.get("run_id")
                    tool_input = event.get("data", {}).get("input", {})
                    tool_calls_executed.append({
                        "id": run_id or f"tool-{len(tool_calls_executed)+1}",
                        "tool": name,
                        "status": "running",
                        "input": tool_input,
                        "output": "",
                    })
                    yield json.dumps({
                        "type": "tool_start",
                        "tool": name,
                        "run_id": run_id,
                        "input": tool_input,
                    })

                elif kind == "on_tool_end":
                    run_id = event.get("run_id")
                    output = event.get("data", {}).get("output", "")
                    if hasattr(output, "content"):
                        output = output.content
                    if len(str(output)) > 4000:
                        output = str(output)[:4000] + "..."
                    for tc in tool_calls_executed:
                        if (run_id and tc["id"] == run_id) or (not run_id and tc["tool"] == name and tc["status"] == "running"):
                            tc["status"] = "done"
                            tc["output"] = str(output)
                            break
                    yield json.dumps({
                        "type": "tool_end",
                        "tool": name,
                        "output": str(output),
                        "run_id": run_id,
                    })

                elif (
                    kind == "on_chain_end"
                    and name == "LangGraph"
                    and root_run_id
                    and event.get("run_id") == root_run_id
                ):
                    for tc in tool_calls_executed:
                        tc["status"] = "done"
                    tc_json = json.dumps(tool_calls_executed, ensure_ascii=False) if tool_calls_executed else None
                    think_json = json.dumps(thinking_data, ensure_ascii=False) if thinking_data.get("content") else None
                    await store.add_message(
                        request.thread_id,
                        "assistant",
                        "".join(assistant_parts),
                        datetime.now(timezone.utc).isoformat(),
                        tool_calls=tc_json,
                        thinking=think_json,
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
