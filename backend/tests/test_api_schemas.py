def test_chat_request_import():
    from src.api.schemas import ChatRequest

    req = ChatRequest(thread_id="t1", message="hello")
    assert req.thread_id == "t1"
    assert req.message == "hello"
