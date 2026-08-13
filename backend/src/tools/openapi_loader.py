import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable

import httpx
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field, create_model

from src.tools.registry import registry
from src.tools.truncate import truncate_text

_MAX_OUTPUT_CHARS = 8000
_TIMEOUT = 30

_client_factory: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(
    timeout=_TIMEOUT
)

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _to_snake_case(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    s2 = re.sub(r"[^a-zA-Z0-9]+", "_", s2)
    return s2.strip("_").lower()


def _path_slug(path: str, method: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_").lower()
    return f"{method}_{slug}"


def _build_args_model(
    params: list[dict], body_schema: dict | None
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    required: list[str] = []
    for p in params:
        ptype = _TYPE_MAP.get(p.get("schema", {}).get("type"), str)
        if p.get("required"):
            fields[p["name"]] = (ptype, Field(description=p.get("description", "")))
            required.append(p["name"])
        else:
            default = p.get("schema", {}).get("default")
            fields[p["name"]] = (
                ptype | None if default is None else ptype,
                Field(default=default, description=p.get("description", "")),
            )
    if body_schema is not None:
        fields["body"] = (dict, Field(default_factory=dict, description="Request JSON body"))
        required.append("body")
    return create_model("OpenApiArgs", **fields)


def _make_operation_tool(
    name: str,
    description: str,
    method: str,
    path_template: str,
    params: list[dict],
    body_schema: dict | None,
    base_url: str,
    token: str | None,
) -> BaseTool:
    args_model = _build_args_model(params, body_schema)
    path_params = {p["name"] for p in params if p.get("in") == "path"}

    @tool(name, description=description, args_schema=args_model)
    def _run(**kwargs: Any) -> str:
        async def _do() -> str:
            url = base_url.rstrip("/") + path_template
            for pname in path_params:
                url = url.replace("{" + pname + "}", str(kwargs.pop(pname)))
            query = {
                k: v for k, v in kwargs.items() if k != "body" and v is not None
            }
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            body = kwargs.get("body")
            try:
                async with _client_factory() as client:
                    response = await client.request(
                        method.upper(), url, params=query, headers=headers, json=body or None
                    )
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return f"ERROR [{exc.response.status_code}]: {exc.response.text[:500]}"
            except httpx.RequestError as exc:
                return f"ERROR [network]: {exc}"
            try:
                text = json.dumps(response.json(), indent=2, ensure_ascii=False)
            except ValueError:
                text = response.text
            return truncate_text(text, _MAX_OUTPUT_CHARS)

        return asyncio.run(_do())

    return _run


def load_openapi_tools(
    spec_path: str | Path,
    base_url: str | None = None,
    token: str | None = None,
) -> list[BaseTool]:
    """Parse an OpenAPI 3.0 JSON spec and return one tool per endpoint."""
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    base_url = base_url or (spec.get("servers") or [{}])[0].get("url", "")
    tools: list[BaseTool] = []
    for path_template, operations in (spec.get("paths") or {}).items():
        for method, op in operations.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = op.get("operationId") or _path_slug(path_template, method)
            name = _to_snake_case(op_id)
            description = op.get("description") or op.get("summary") or name
            params = list(op.get("parameters") or [])
            body_schema = op.get("requestBody")
            op_tool = _make_operation_tool(
                name, description, method, path_template, params, body_schema,
                base_url, token,
            )
            registry.register(group="api", name=name)(op_tool)
            tools.append(op_tool)
    return tools
