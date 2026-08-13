import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable

import httpx
from langchain_core.tools import BaseTool, StructuredTool
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


def _resolve_ref(ref: str, spec: dict) -> dict | None:
    """Resolve a local OpenAPI $ref like '#/components/parameters/X'."""
    if not ref.startswith("#/"):
        return None
    parts = ref[2:].split("/")
    node: Any = spec
    for part in parts:
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
        if node is None:
            return None
    return node if isinstance(node, dict) else None


def _build_args_model(
    params: list[dict], body_schema: dict | None
) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for p in params:
        ptype = _TYPE_MAP.get(p.get("schema", {}).get("type"), str)
        if p.get("required"):
            fields[p["name"]] = (ptype, Field(description=p.get("description", "")))
        else:
            default = p.get("schema", {}).get("default")
            fields[p["name"]] = (
                ptype | None if default is None else ptype,
                Field(default=default, description=p.get("description", "")),
            )
    if body_schema is not None:
        fields["body"] = (dict, Field(default_factory=dict, description="Request JSON body"))
    # Pydantic infers requiredness from the presence/absence of a default:
    # fields without a default are required; body stays optional by design.
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
    header_params = {p["name"] for p in params if p.get("in") == "header"}
    cookie_params = {p["name"] for p in params if p.get("in") == "cookie"}

    async def _do(**kwargs: Any) -> str:
        url = base_url.rstrip("/") + path_template
        for pname in path_params:
            url = url.replace("{" + pname + "}", str(kwargs.pop(pname)))
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        for hname in header_params:
            hval = kwargs.pop(hname, None)
            if hval is not None:
                headers[hname] = str(hval)
        cookie_parts = []
        for cname in cookie_params:
            cval = kwargs.pop(cname, None)
            if cval is not None:
                cookie_parts.append(f"{cname}={cval}")
        if cookie_parts:
            headers["Cookie"] = "; ".join(cookie_parts)
        query = {
            k: v for k, v in kwargs.items() if k != "body" and v is not None
        }
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

    def sync_wrapper(**kwargs: Any) -> str:
        return asyncio.run(_do(**kwargs))

    return StructuredTool.from_function(
        func=sync_wrapper,
        coroutine=_do,
        name=name,
        description=description,
        args_schema=args_model,
    )


def load_openapi_tools(
    spec_path: str | Path,
    base_url: str | None = None,
    token: str | None = None,
) -> list[BaseTool]:
    """Parse an OpenAPI 3.0 JSON spec and return one tool per endpoint."""
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    base_url = base_url or (spec.get("servers") or [{}])[0].get("url", "") or ""
    tools: list[BaseTool] = []
    existing_names = {t.name for t in registry.all_tools()}
    for path_template, operations in (spec.get("paths") or {}).items():
        for method, op in operations.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            op_id = op.get("operationId") or _path_slug(path_template, method)
            name = _to_snake_case(op_id)
            description = op.get("description") or op.get("summary") or name
            params = []
            for p in op.get("parameters") or []:
                if "$ref" in p:
                    resolved = _resolve_ref(p["$ref"], spec)
                    if resolved is None:
                        continue  # skip unresolvable ref — tools never raise
                    p = resolved
                params.append(p)
            body_schema = op.get("requestBody")
            if body_schema and "$ref" in body_schema:
                resolved = _resolve_ref(body_schema["$ref"], spec)
                body_schema = resolved if resolved is not None else None
            op_tool = _make_operation_tool(
                name, description, method, path_template, params, body_schema,
                base_url, token,
            )
            if name not in existing_names:
                registry.register(group="api", name=name)(op_tool)
                existing_names.add(name)
            tools.append(op_tool)
    return tools
