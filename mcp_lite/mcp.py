"""Hand-rolled MCP (Model Context Protocol) server core -- JSON-RPC 2.0
message handling plus a tool/resource registry, written from scratch after
reading fastapi_mcp's source (github.com/tadata-org/fastapi_mcp) rather than
depending on it or the official `mcp` SDK. The point of this file: once you
strip the library away, "expose tools over MCP" is JSON-RPC, a handful of
methods, and a couple of lists of {name, description, schema} -- worth
seeing directly instead of trusting a package to do it.

# Scope, stated up front (see README.md for the full list with reasons)
Implements: `initialize`, `notifications/initialized`, `tools/list`,
`tools/call` (with progress notifications and cancellation), `resources/list`,
`resources/read`, and JSON-RPC batch requests (a JSON array of messages in
one call). Session IDs, SSE framing, and bearer-token auth are real
MCP/transport features too, but none of them are JSON-RPC *methods* --
they're HTTP-level concerns, so they live in transport.py instead of here.
Still not implemented anywhere in this project: prompts, sampling, roots,
elicitation, subscriptions. Each is a real protocol capability -- skipped
because none of them change what "a tool call" or "a resource read"
fundamentally is, which is the thing worth understanding by hand.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

# progress(current, total, message) -- total/message are optional per spec.
ProgressFn = Callable[[float, "float | None", "str | None"], Awaitable[None]]
ToolFn = Callable[[dict[str, Any], ProgressFn], Awaitable[Any]]
ResourceFn = Callable[[], Awaitable[str]]

PROTOCOL_VERSION = "2025-06-18"


async def _noop_progress(progress: float, total: float | None = None, message: str | None = None) -> None:
    """The default a tool's `report_progress` gets when no one's listening
    (no progressToken, or the transport can't stream) -- every tool can
    unconditionally call it without checking for None first.
    """


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    call: ToolFn
    # readOnlyHint/destructiveHint/idempotentHint/openWorldHint -- lets a
    # client's UI warn before a destructive call or auto-approve a read-only
    # one, instead of treating every tool call the same way.
    annotations: dict[str, Any] | None = None

    def to_mcp_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.annotations:
            schema["annotations"] = self.annotations
        return schema


@dataclass
class Resource:
    """Read-only, URI-addressed data -- a different *kind* of thing from a
    Tool. A tool is an action a client asks the server to perform; a
    resource is data a client can read without triggering one. `read`
    takes no arguments (unlike a tool call) for exactly that reason.
    """

    uri: str
    name: str
    description: str
    mime_type: str
    read: ResourceFn

    def to_mcp_schema(self) -> dict[str, Any]:
        return {"uri": self.uri, "name": self.name, "description": self.description, "mimeType": self.mime_type}


class MCPServer:
    """Tool/resource registry + JSON-RPC dispatch. Transport-agnostic: hand
    it whatever message(s) came off the wire, it hands back whatever
    belongs on the wire in response (or None, for an all-notifications
    call). app.py and transport.py own the actual HTTP endpoint, sessions,
    and auth.
    """

    def __init__(self, name: str, version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self.tools: dict[str, Tool] = {}
        self.resources: dict[str, Resource] = {}
        # ponytail: keyed by request id alone, not (session, id) -- fine for
        # one client at a time exercising this by hand; two concurrent
        # clients that happen to reuse the same id could cancel each
        # other's call. Key by session too if that ever matters.
        self._in_flight: dict[Any, asyncio.Task[Any]] = {}

    def register(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def register_resource(self, resource: Resource) -> None:
        self.resources[resource.uri] = resource

    async def handle(
        self, payload: dict[str, Any] | list[dict[str, Any]]
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Accepts either one JSON-RPC message or a batch (a JSON array of
        them), per the spec's batching rule. A batch of all notifications
        produces no responses at all -- same "notifications get nothing
        back" rule as a single message, just applied per-item and collected.

        # ponytail: assumes a session already exists for any batch (i.e. no
        # `initialize` inside a batch establishes a new one) -- transport.py
        # only creates a session for a bare, non-batched `initialize` call.
        # Real clients don't batch their very first handshake message in
        # practice; revisit if one does.
        """
        if isinstance(payload, list):
            responses = [r for message in payload if (r := await self._handle_one(message)) is not None]
            return responses or None
        return await self._handle_one(payload)

    async def _handle_one(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if message.get("jsonrpc") != "2.0" or "method" not in message:
            return self._error(message.get("id"), -32600, "Invalid Request")

        method = message["method"]
        msg_id = message.get("id")
        params = message.get("params") or {}

        if method == "notifications/cancelled":
            # Handled *before* the generic "notification -> no response"
            # return below, since -- unlike every other notification here --
            # this one needs to actually do something: it's the client
            # asking the server to stop a request it already sent, most
            # usefully one still running via a concurrent HTTP request (see
            # transport.py's streaming path, where this is actually reachable).
            self.cancel(params.get("requestId"))
            return None

        if msg_id is None:
            # No "id" means the client sent a *notification* -- it isn't
            # listening for a reply. Responding to one anyway is a real,
            # subtle protocol bug, not just an unnecessary courtesy.
            return None

        if method == "initialize":
            capabilities: dict[str, Any] = {"tools": {"listChanged": False}}
            if self.resources:
                capabilities["resources"] = {"subscribe": False, "listChanged": False}
            return self._result(
                msg_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": capabilities,
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            )

        if method == "tools/list":
            return self._result(msg_id, {"tools": [t.to_mcp_schema() for t in self.tools.values()]})

        if method == "tools/call":
            return await self.call_tool(msg_id, params)

        if method == "resources/list":
            return self._result(msg_id, {"resources": [r.to_mcp_schema() for r in self.resources.values()]})

        if method == "resources/read":
            return await self._read_resource(msg_id, params)

        if method == "ping":
            # Clients (and some proxies) ping to check the connection is
            # still alive. Empty result is the entire spec for this one.
            return self._result(msg_id, {})

        return self._error(msg_id, -32601, f"Method not found: {method}")

    async def call_tool(
        self, msg_id: Any, params: dict[str, Any], report_progress: ProgressFn | None = None
    ) -> dict[str, Any]:
        name = params.get("name")
        tool = self.tools.get(name)
        if tool is None:
            return self._error(msg_id, -32602, f"Unknown tool: {name}")

        # Wrapped in a real Task (not just awaited inline) specifically so
        # `cancel()` -- reachable from a *different*, concurrent HTTP
        # request carrying `notifications/cancelled` -- has something to
        # call .cancel() on. Registered under msg_id for exactly that call
        # to find; cleared in `finally` so a finished/failed call can't be
        # "cancelled" after the fact.
        task = asyncio.ensure_future(tool.call(params.get("arguments") or {}, report_progress or _noop_progress))
        self._in_flight[msg_id] = task
        try:
            result = await task
        except asyncio.CancelledError:
            # Deliberately swallowed, not re-raised: from the client's side
            # this is a completed tool call whose answer is "cancelled",
            # not a broken connection. See README's honest caveat -- the
            # *asyncio* task stops waiting here, but if the tool was
            # blocked in a sync call via asyncio.to_thread (ask_agent is),
            # the underlying OS thread has no way to be interrupted and
            # keeps running to completion in the background regardless.
            return self._result(msg_id, {"content": [{"type": "text", "text": "cancelled"}], "isError": True})
        except Exception as e:  # noqa: BLE001 -- tool boundary: any failure becomes isError, not a crash
            # A tool that raises is reported *inside* a normal JSON-RPC
            # success response with isError=True, not as a JSON-RPC error --
            # that's the MCP spec's own distinction between "the protocol
            # call itself failed" and "the tool ran and its work failed".
            return self._result(msg_id, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
        finally:
            self._in_flight.pop(msg_id, None)

        # A plain str result becomes the text verbatim. Anything else (a
        # dict/list from a REST endpoint's JSON body, say) gets
        # json.dumps'd -- str() on a dict produces Python repr syntax
        # ({'a': 1}, single-quoted, not valid JSON), which silently breaks
        # any client that tries to parse a tool's text output as JSON.
        # structuredContent (2025-06-18 spec addition) hands the same data
        # back as real JSON too, so a client doesn't have to parse text at
        # all when it doesn't need to.
        payload: dict[str, Any] = {"content": [{"type": "text", "text": result if isinstance(result, str) else json.dumps(result)}]}
        if isinstance(result, dict):
            # Spec requires structuredContent to be a JSON *object* -- a
            # list result still gets valid JSON text above, just not this.
            payload["structuredContent"] = result
        return self._result(msg_id, payload)

    def cancel(self, request_id: Any) -> bool:
        """Best-effort: returns False silently for an unknown/already-
        finished request id rather than raising -- a cancellation notice
        that loses a race with the call finishing naturally is normal, not
        an error either side needs to handle specially.
        """
        task = self._in_flight.get(request_id)
        if task is None:
            return False
        task.cancel()
        return True

    async def _read_resource(self, msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri")
        resource = self.resources.get(uri)
        if resource is None:
            return self._error(msg_id, -32602, f"Unknown resource: {uri}")
        text = await resource.read()
        return self._result(msg_id, {"contents": [{"uri": resource.uri, "mimeType": resource.mime_type, "text": text}]})

    @staticmethod
    def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def demo() -> None:
    async def echo(arguments: dict[str, Any], report_progress: ProgressFn) -> str:
        return f"you said: {arguments.get('text')}"

    async def boom(arguments: dict[str, Any], report_progress: ProgressFn) -> str:
        raise ValueError("tool blew up")

    async def get_status(arguments: dict[str, Any], report_progress: ProgressFn) -> dict[str, Any]:
        return {"ok": True, "count": 3}

    async def slow_with_progress(arguments: dict[str, Any], report_progress: ProgressFn) -> str:
        for step in range(3):
            await report_progress(step, 3, f"step {step}")
            await asyncio.sleep(0.05)
        return "finished all steps"

    async def sleeps_forever(arguments: dict[str, Any], report_progress: ProgressFn) -> str:
        await asyncio.sleep(60)
        return "should never get here"

    async def read_greeting() -> str:
        return "hello from a resource"

    server = MCPServer(name="demo")
    server.register(
        Tool(
            "echo",
            "Echoes text back",
            {"type": "object", "properties": {"text": {"type": "string"}}},
            echo,
            annotations={"readOnlyHint": True},
        )
    )
    server.register(Tool("boom", "Always fails", {"type": "object", "properties": {}}, boom))
    server.register(Tool("get_status", "Returns a status object", {"type": "object", "properties": {}}, get_status))
    server.register(Tool("slow", "Reports progress across 3 steps", {"type": "object", "properties": {}}, slow_with_progress))
    server.register(Tool("forever", "Never returns on its own", {"type": "object", "properties": {}}, sleeps_forever))
    server.register_resource(
        Resource("res://greeting", "Greeting", "A static greeting", "text/plain", read_greeting)
    )

    async def run() -> None:
        init = await server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert init["result"]["protocolVersion"] == PROTOCOL_VERSION
        assert "resources" in init["result"]["capabilities"], "registering a resource should advertise the capability"

        note = await server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert note is None, "a notification must get no response"

        listed = await server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools_by_name = {t["name"]: t for t in listed["result"]["tools"]}
        assert set(tools_by_name) == {"echo", "boom", "get_status", "slow", "forever"}
        assert tools_by_name["echo"]["annotations"] == {"readOnlyHint": True}
        assert "annotations" not in tools_by_name["boom"], "no annotations set means the key is just absent"

        called = await server.handle(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "hi"}}}
        )
        assert called["result"]["content"][0]["text"] == "you said: hi"

        status_call = await server.handle(
            {"jsonrpc": "2.0", "id": 30, "method": "tools/call", "params": {"name": "get_status", "arguments": {}}}
        )
        # A dict result must come back as valid JSON text (not Python repr)
        # *and* as structuredContent -- both checked directly.
        assert json.loads(status_call["result"]["content"][0]["text"]) == {"ok": True, "count": 3}
        assert status_call["result"]["structuredContent"] == {"ok": True, "count": 3}

        pong = await server.handle({"jsonrpc": "2.0", "id": 31, "method": "ping"})
        assert pong["result"] == {}

        failed = await server.handle(
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "boom", "arguments": {}}}
        )
        assert failed["result"]["isError"] is True

        missing_tool = await server.handle(
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "nope", "arguments": {}}}
        )
        assert missing_tool["error"]["code"] == -32602

        missing_method = await server.handle({"jsonrpc": "2.0", "id": 6, "method": "nope"})
        assert missing_method["error"]["code"] == -32601

        invalid = await server.handle({"not": "jsonrpc"})
        assert invalid["error"]["code"] == -32600

        listed_res = await server.handle({"jsonrpc": "2.0", "id": 7, "method": "resources/list"})
        uris = {r["uri"] for r in listed_res["result"]["resources"]}
        assert uris == {"res://greeting"}

        read = await server.handle(
            {"jsonrpc": "2.0", "id": 8, "method": "resources/read", "params": {"uri": "res://greeting"}}
        )
        assert read["result"]["contents"][0]["text"] == "hello from a resource"

        missing_resource = await server.handle(
            {"jsonrpc": "2.0", "id": 9, "method": "resources/read", "params": {"uri": "res://nope"}}
        )
        assert missing_resource["error"]["code"] == -32602

        # Progress: call_tool() directly (not handle()) since progress is
        # the one thing plain single-response JSON-RPC has no room to
        # carry -- a real transport has to choose to stream to get this at
        # all (see transport.py's stream_tool_call_with_progress).
        progress_events: list[tuple[float, float | None, str | None]] = []

        async def capture_progress(progress: float, total: float | None = None, message: str | None = None) -> None:
            progress_events.append((progress, total, message))

        slow_result = await server.call_tool(40, {"name": "slow", "arguments": {}}, capture_progress)
        assert slow_result["result"]["content"][0]["text"] == "finished all steps"
        assert progress_events == [(0, 3, "step 0"), (1, 3, "step 1"), (2, 3, "step 2")]

        # Cancellation: start a call that never finishes on its own, cancel
        # it mid-flight via the same `notifications/cancelled` path a
        # concurrent HTTP request would use, and confirm the *caller*
        # (whoever's awaiting call_tool) gets a clean "cancelled" result
        # rather than an unhandled CancelledError.
        cancel_task = asyncio.ensure_future(server.call_tool(41, {"name": "forever", "arguments": {}}))
        await asyncio.sleep(0.01)  # let call_tool register the task in _in_flight before cancelling it
        cancelled_by_unknown_id = server.cancel(9999)
        assert cancelled_by_unknown_id is False, "cancelling an id nothing is running under must be a no-op, not an error"
        cancelled = await server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 41}})
        assert cancelled is None, "notifications/cancelled is itself a notification -- no response"
        cancel_result = await cancel_task
        assert cancel_result["result"]["isError"] is True
        assert cancel_result["result"]["content"][0]["text"] == "cancelled"

        # Batch: two real requests + one notification mixed together --
        # only the two requests get responses, in order.
        batch = await server.handle(
            [
                {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "a"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "b"}}},
            ]
        )
        assert [r["id"] for r in batch] == [10, 11]
        assert [r["result"]["content"][0]["text"] for r in batch] == ["you said: a", "you said: b"]

        all_notifications = await server.handle(
            [{"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "method": "notifications/initialized"}]
        )
        assert all_notifications is None, "an all-notification batch must get no response"

    asyncio.run(run())
    print("mcp.py: ok")


if __name__ == "__main__":
    demo()
