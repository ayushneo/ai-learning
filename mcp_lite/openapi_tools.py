"""FastAPI OpenAPI schema -> Tool objects: pattern (a), individual REST
endpoints become MCP tools automatically. Same trick fastapi_mcp uses
internally (confirmed by reading its `openapi/convert.py` and `server.py`
directly) -- snapshot the app's own OpenAPI schema, then dispatch each tool
call back into the app *in-process* via an ASGI transport instead of a real
network round trip. Reimplemented by hand here, deliberately narrower:

# ponytail: only GET-with-query-params and POST-with-a-JSON-body are
# handled (no path params, headers, cookies, or file uploads). Covers this
# project's two demo endpoints; extend `_build_tool` for more shapes.
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI

from mcp_lite.mcp import ProgressFn, Tool


def tools_from_app(app: FastAPI, client: httpx.AsyncClient) -> list[Tool]:
    # NOTE: app.openapi() snapshots the schema and caches it on first call --
    # every route meant to become a tool must already be registered before
    # this runs. Routes added to `app` afterward won't appear here even
    # though FastAPI itself will still happily serve them.
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})

    return [
        _build_tool(path, method, operation, components, client)
        for path, methods in schema["paths"].items()
        for method, operation in methods.items()
        if method.lower() in ("get", "post")
    ]


def _resolve_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return components.get(name, {})
    return schema


def _build_tool(
    path: str,
    method: str,
    operation: dict[str, Any],
    components: dict[str, Any],
    client: httpx.AsyncClient,
) -> Tool:
    # operationId is what FastAPI (and fastapi_mcp) call the tool's *name*.
    # FastAPI always fills one in -- auto-derived from the function name and
    # path if you didn't set one -- so the real risk isn't a missing name,
    # it's an unstable one: rename the function or move the router, and an
    # auto-generated operationId silently changes, quietly renaming the
    # tool from an agent's perspective. Set `operation_id=` explicitly on
    # any route you want a stable tool identity for (see app.py).
    name = operation["operationId"]
    # `description` (the route's docstring) over `summary` (FastAPI's
    # auto-derived one-liner from the function name) -- the docstring is the
    # one a human actually wrote on purpose.
    description = operation.get("description") or operation.get("summary") or name

    if method.lower() == "post" and "requestBody" in operation:
        body_schema = operation["requestBody"]["content"]["application/json"]["schema"]
        input_schema = _resolve_schema(body_schema, components)

        # report_progress is unused here -- a REST call is one round trip,
        # nothing mid-call to report. Still part of the signature: every
        # Tool.call takes (arguments, report_progress) uniformly, so
        # MCPServer.call_tool never needs to know which tools care.
        async def call(arguments: dict[str, Any], report_progress: ProgressFn, _path: str = path) -> Any:
            resp = await client.post(_path, json=arguments)
            resp.raise_for_status()
            return resp.json()
    else:
        parameters = operation.get("parameters", [])
        input_schema = {
            "type": "object",
            "properties": {p["name"]: p.get("schema", {"type": "string"}) for p in parameters},
            "required": [p["name"] for p in parameters if p.get("required")],
        }

        async def call(arguments: dict[str, Any], report_progress: ProgressFn, _path: str = path) -> Any:
            resp = await client.get(_path, params=arguments)
            resp.raise_for_status()
            return resp.json()

    # A GET with no request body is the closest thing OpenAPI gives us to
    # "this doesn't change anything" -- good enough for a default hint. Not
    # a guarantee (nothing stops a GET handler from having a side effect);
    # override per-route if that's ever actually true here.
    annotations = {"readOnlyHint": method.lower() == "get"}

    return Tool(name=name, description=description, input_schema=input_schema, call=call, annotations=annotations)
