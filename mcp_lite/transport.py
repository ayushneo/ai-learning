"""HTTP-transport concerns for the Streamable HTTP MCP transport, kept
separate from the JSON-RPC core (mcp.py) since none of this is part of the
protocol *payload* -- it's headers, status codes, and response framing that
sit around a JSON-RPC message, not inside one.

# Session lifecycle
The server assigns an opaque id when a client calls `initialize`, returned
via the `Mcp-Session-Id` response header (never in the JSON-RPC body
itself). Every later request on that logical connection must echo the same
header; requests without a valid one are rejected before they ever reach
mcp.py. A client ends a session with `DELETE /mcp`.

# ponytail: sessions live in a plain in-process set -- gone on restart, not
# shared across worker processes. Fine for one uvicorn worker (this
# project's whole point is being readable, not horizontally scaled); a real
# multi-worker deployment needs a shared store (Redis, a DB row) instead.

# Auth
`verify_bearer_token` is a plain FastAPI `Depends()` -- not a bespoke
MCP-specific auth path. That's the actual idea behind fastapi_mcp's
`AuthConfig(dependencies=[...])`: bridge MCP auth onto FastAPI's own
dependency injection instead of inventing a parallel mechanism. Opt-in via
the `MCP_LITE_TOKEN` env var so the demo/tests keep working with zero setup.
This is a *static shared secret*, not OAuth -- enough for a client that lets
you configure a bearer token directly (Claude Code's `claude mcp add
--header`, OpenAI's Responses API `headers`), not enough for Claude.ai's
web "Custom Connector" UI, which requires a real OAuth flow. See README.

# Origin validation
The spec calls this out explicitly: a server MUST validate the `Origin`
header on every request to prevent DNS rebinding (a malicious webpage's own
JS fetching a server bound to localhost, riding the browser's trust of
localhost). Non-browser MCP clients (Claude Desktop, a Python httpx client)
generally don't send `Origin` at all, so they're unaffected; a browser-based
client's Origin must be explicitly allowlisted via `MCP_LITE_ALLOWED_ORIGINS`
(comma-separated) or it's rejected -- deny-by-default, not allow-by-default.

# Progress streaming
`stream_tool_call_with_progress` is the one place this project sends more
than one message per HTTP response: while a tool call is running, it can
call its `report_progress` (see mcp.py) any number of times, each becoming
a `notifications/progress` SSE event, before the final JSON-RPC response
event closes the stream. `sse_response` above can't do this -- it only
wraps one *already-finished* response. Still not implemented: a `GET /mcp`
stream for messages pushed outside the lifetime of any single request (this
project has no source for those -- no subscriptions, no sampling).
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from fastapi import Header, HTTPException, status
from fastapi.responses import Response

if TYPE_CHECKING:
    from mcp_lite.mcp import MCPServer

SUPPORTED_PROTOCOL_VERSIONS = {"2025-06-18", "2025-03-26"}


class SessionStore:
    def __init__(self) -> None:
        self._sessions: set[str] = set()

    def create(self) -> str:
        session_id = uuid.uuid4().hex
        self._sessions.add(session_id)
        return session_id

    def valid(self, session_id: str | None) -> bool:
        return session_id is not None and session_id in self._sessions

    def terminate(self, session_id: str | None) -> None:
        if session_id is not None:
            self._sessions.discard(session_id)


def verify_bearer_token(authorization: str | None = Header(None)) -> None:
    expected = os.environ.get("MCP_LITE_TOKEN")
    if expected is None:
        return  # auth is opt-in; unset means disabled, not "misconfigured"
    if authorization != f"Bearer {expected}":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid bearer token")


def verify_origin(origin: str | None = Header(None)) -> None:
    if origin is None:
        return  # most MCP clients (anything not running in a browser) never send one
    allowed = {o.strip() for o in os.environ.get("MCP_LITE_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    if origin not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"origin not allowed: {origin}")


def verify_protocol_version(mcp_protocol_version: str | None = Header(None, alias="MCP-Protocol-Version")) -> None:
    # ponytail: permissive when the header is absent -- plenty of clients
    # deployed before this header existed still work fine, and mcp.py's
    # `initialize` response is what actually tells a client which version
    # this server speaks. Only reject a version we *know* we don't handle.
    if mcp_protocol_version is not None and mcp_protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsupported MCP-Protocol-Version: {mcp_protocol_version}")


def sse_response(payload: dict[str, Any]) -> Response:
    """Wrap one JSON-RPC response as a single Server-Sent Event. The
    Streamable HTTP transport lets a client request this via
    `Accept: text/event-stream` on POST (several real clients, e.g. the MCP
    Inspector, default to sending it) -- the server may reply with plain
    JSON or one SSE event either way. This project never has more than one
    event to send per request (no server-initiated push is implemented --
    see README's Session/SSE row), so it's one `data:` line, not an actual
    live stream.
    """
    body = f"event: message\ndata: {json.dumps(payload)}\n\n"
    return Response(content=body, media_type="text/event-stream")


_PROGRESS_POLL_INTERVAL = 0.05


async def stream_tool_call_with_progress(
    mcp: MCPServer, msg_id: Any, params: dict[str, Any], progress_token: Any
) -> AsyncIterator[bytes]:
    """Run one `tools/call` as a real SSE stream: zero or more
    `notifications/progress` events while it's in flight, then exactly one
    final `message` event carrying the actual JSON-RPC response.

    # ponytail: polls a queue on a short timer instead of a cleaner
    # asyncio.Event-based wakeup -- simpler to read, costs up to
    # _PROGRESS_POLL_INTERVAL of latency per event reaching the wire.
    # Irrelevant at this project's scale; a high-frequency-progress tool
    # would want the event-based version instead.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def report_progress(progress: float, total: float | None = None, message: str | None = None) -> None:
        notification_params: dict[str, Any] = {"progressToken": progress_token, "progress": progress}
        if total is not None:
            notification_params["total"] = total
        if message is not None:
            notification_params["message"] = message
        await queue.put({"jsonrpc": "2.0", "method": "notifications/progress", "params": notification_params})

    # A real Task, not just an awaited coroutine, so this generator can keep
    # draining the progress queue *while* the call is still running instead
    # of only seeing progress events after the fact.
    task = asyncio.ensure_future(mcp.call_tool(msg_id, params, report_progress))

    while not task.done():
        try:
            event = await asyncio.wait_for(queue.get(), timeout=_PROGRESS_POLL_INTERVAL)
        except asyncio.TimeoutError:
            continue
        yield f"event: message\ndata: {json.dumps(event)}\n\n".encode()

    # The task may have queued its last progress event and finished in the
    # same tick the loop above last timed out on -- drain what's left
    # before sending the final response so nothing arrives out of order.
    while not queue.empty():
        yield f"event: message\ndata: {json.dumps(queue.get_nowait())}\n\n".encode()

    yield f"event: message\ndata: {json.dumps(task.result())}\n\n".encode()
