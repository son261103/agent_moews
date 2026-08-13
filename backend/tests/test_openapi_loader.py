import asyncio
import json

import httpx
import pytest

import src.tools.openapi_loader as loader

SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com"}],
    "components": {
        "parameters": {
            "LimitParam": {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "default": 10},
            }
        }
    },
    "paths": {
        "/v1/users": {
            "get": {
                "operationId": "User_findAll",
                "description": "List users",
                "parameters": [
                    {"name": "page", "in": "query", "required": False,
                     "schema": {"type": "integer", "default": 1}},
                    {"name": "q", "in": "query", "required": True,
                     "schema": {"type": "string"}},
                ],
            }
        },
        "/v1/users/{id}": {
            "get": {
                "operationId": "User_findOne",
                "description": "Get one user",
                "parameters": [
                    {"name": "id", "in": "path", "required": True,
                     "schema": {"type": "integer"}},
                ],
            }
        },
        "/v1/tenants": {
            "get": {
                "operationId": "Tenant_list",
                "description": "List tenants",
                "parameters": [
                    {"$ref": "#/components/parameters/LimitParam"},
                ],
            }
        },
    },
}

HEADER_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/v1/tenants": {
            "get": {
                "operationId": "Tenant_list",
                "description": "List tenants",
                "parameters": [
                    {"name": "X-Tenant-Id", "in": "header", "required": True,
                     "schema": {"type": "string"}},
                ],
            }
        },
    },
}


def _write_spec(tmp_path) -> str:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(SPEC), encoding="utf-8")
    return str(p)


def _write_header_spec(tmp_path) -> str:
    p = tmp_path / "header_spec.json"
    p.write_text(json.dumps(HEADER_SPEC), encoding="utf-8")
    return str(p)


@pytest.fixture(autouse=True)
def _clear_registry():
    from src.tools.registry import registry
    saved_tools = dict(registry._tools)
    saved_groups = dict(registry._groups)
    registry._tools.clear()
    registry._groups.clear()
    yield
    registry._tools.clear()
    registry._groups.clear()
    registry._tools.update(saved_tools)
    registry._groups.update(saved_groups)


def test_generates_one_tool_per_operation(tmp_path):
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="tok")
    names = sorted(t.name for t in tools)
    assert names == ["tenant_list", "user_find_all", "user_find_one"]


def test_required_args_in_schema(tmp_path):
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local")
    tool_by_name = {t.name: t for t in tools}
    schema = tool_by_name["user_find_all"].args_schema.model_json_schema()
    props = schema["properties"]
    assert "q" in props and "page" in props
    assert schema["required"] == ["q"]  # only the required query param


def test_invoke_builds_url_headers_and_returns_json(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"name": "Moew"}]})

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="sekret")
    try:
        result = tools[0].invoke({"q": "cat", "page": 2})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    assert captured["url"] == "http://test.local/v1/users?page=2&q=cat"
    assert captured["auth"] == "Bearer sekret"
    assert '"name": "Moew"' in result


def test_path_param_substitution(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"id": 7})

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local")
    try:
        tools[1].invoke({"id": 7})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    assert captured["url"] == "http://test.local/v1/users/7"


def test_http_error_returns_structured_string(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="bad")
    try:
        result = tools[0].invoke({"q": "x"})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    assert result.startswith("ERROR [401]")


def test_header_param_sent_in_headers_not_query(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(
        _write_header_spec(tmp_path), base_url="http://test.local", token="tok"
    )
    try:
        result = tools[0].invoke({"X-Tenant-Id": "tenant-123"})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    # Header param must land in request headers, not the query string
    assert captured["headers"].get("x-tenant-id") == "tenant-123"
    assert "?" not in captured["url"]
    assert captured["url"] == "http://test.local/v1/tenants"
    assert '"ok": true' in result


def test_ref_param_resolved(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True})

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="tok")
    try:
        result = tools[2].invoke({"limit": 5})
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    # $ref param resolved to a query param and sent in the URL
    assert "limit=5" in captured["url"]
    assert '"ok": true' in result


def test_load_openapi_tools_idempotent(tmp_path):
    spec_path = _write_spec(tmp_path)
    loader.load_openapi_tools(spec_path, base_url="http://test.local")
    # Second call must not raise (registry already has these names)
    loader.load_openapi_tools(spec_path, base_url="http://test.local")
    from src.tools.registry import registry
    api_tools = registry.tools_by_group("api")
    names = [t.name for t in api_tools]
    assert names.count("user_find_all") == 1
    assert names.count("user_find_one") == 1
    assert names.count("tenant_list") == 1


def test_async_invoke_works(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"data": [{"name": "Moew"}]})

    loader._client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=30
    )
    tools = loader.load_openapi_tools(_write_spec(tmp_path), base_url="http://test.local", token="sekret")
    try:
        result = asyncio.run(tools[0].ainvoke({"q": "cat", "page": 2}))
    finally:
        loader._client_factory = lambda: httpx.AsyncClient(timeout=30)
    assert captured["url"] == "http://test.local/v1/users?page=2&q=cat"
    assert captured["auth"] == "Bearer sekret"
    assert '"name": "Moew"' in result
