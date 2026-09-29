"""Demo app tying it all together over the hand-rolled core in mcp.py and
transport.py -- no `fastapi_mcp`, no `mcp` SDK anywhere in this project.

(a) Individual REST endpoints as MCP tools: /calculator and /search below
    reuse react_agent's own tool functions, and openapi_tools.tools_from_app()
    converts them into MCP tools automatically from the OpenAPI schema.

(b) A whole internal agent loop as one meta-tool: react_agent's ReAct loop
    (react_agent.agent.run_agent) isn't a REST endpoint, so there's no
    OpenAPI operation to convert -- it's registered directly as a hand-built
    Tool instead. From an MCP client's view this is a single opaque
    "ask_agent(question)" box, in contrast to (a)'s two separately-callable
    tools -- the same (a)-vs-(b) trade-off already recorded in
    react_mcp_server/react-mcp-server-spec.md, built here instead of only
    described.

Plus a Resource (read-only data, not an action): react_agent's own few-shot
prompt template, exposed so a client can *read* how the agent is steered
without that being a callable tool.

Run: fastapi dev mcp_lite/app.py -- REST at /calculator, /search; MCP at /mcp.
Set MCP_LITE_TOKEN to require a bearer token on /mcp (see transport.py).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from mcp_lite.mcp import MCPServer, ProgressFn, Resource, Tool
from mcp_lite.openapi_tools import tools_from_app
from mcp_lite.transport import (
    SessionStore,
    sse_response,
    stream_tool_call_with_progress,
    verify_bearer_token,
    verify_origin,
    verify_protocol_version,
)
from react_agent.agent import run_agent
from react_agent.prompt import TEMPLATE as REACT_PROMPT_TEMPLATE
from react_agent.tools import calculator, search

app = FastAPI(title="mcp-lite-demo")

# Only matters for browser-based clients (Claude.ai web, ChatGPT web) --
# non-browser MCP clients ignore CORS entirely. Mcp-Session-Id must be
# explicitly exposed: browsers hide custom response headers from JS unless
# a CORS response says otherwise, so without this a browser client could
# receive the header on the wire and still be unable to read it.
_allowed_origins = [o.strip() for o in os.environ.get("MCP_LITE_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )


class CalculatorInput(BaseModel):
    expression: str = Field(..., description="A basic arithmetic expression, e.g. '12 * (4 + 1)'")


class SearchInput(BaseModel):
    query: str = Field(..., description="A search query, e.g. a factual question")


@app.post("/calculator", operation_id="calculator")
async def calculator_endpoint(input: CalculatorInput) -> dict[str, str]:
    """Evaluate a basic arithmetic expression and return the numeric result."""
    return {"result": calculator(input.expression)}


@app.post("/search", operation_id="search")
async def search_endpoint(input: SearchInput) -> dict[str, str]:
    """Look up a query on Wikipedia and return a short text summary."""
    return {"result": search(input.query)}


def make_ask_agent_tool(llm: Callable[..., str] | None = None) -> Tool:
    """Factory (not a module-level singleton) so tests can inject a fake
    `llm`, the same way react_agent.agent's own demo() does -- without it,
    every call here would hit the real Anthropic API.
    """

    async def call(arguments: dict[str, Any], report_progress: ProgressFn) -> str:
        # run_agent is sync and can block on a real network call; to_thread
        # keeps it off the event loop instead of stalling every other
        # request while one agent call is in flight.
        #
        # on_step runs *inside that worker thread*, not on the event loop --
        # run_coroutine_threadsafe is the actual bridge back: it schedules
        # report_progress's coroutine onto the loop from another thread
        # safely, which a bare `await` from a sync function cannot do.
        loop = asyncio.get_running_loop()

        def on_step(step: int, message: str) -> None:
            asyncio.run_coroutine_threadsafe(report_progress(step, None, message), loop)

        return await asyncio.to_thread(run_agent, arguments["question"], llm=llm, on_step=on_step)

    return Tool(
        name="ask_agent",
        description=(
            "Ask the hand-rolled ReAct agent a question; it may use a calculator "
            "or web search internally before giving a final answer."
        ),
        input_schema={
            "type": "object",
            "properties": {"question": {"type": "string", "description": "The question to ask the agent."}},
            "required": ["question"],
        },
        call=call,
        # Not read-only (it can reach out to the network via search/an LLM
        # call) and not idempotent (the same question can get a different
        # answer next time) -- worth being honest about both in the hint.
        annotations={"readOnlyHint": False, "idempotentHint": False},
    )


mcp = MCPServer(name=app.title)
sessions = SessionStore()

# Pattern (a): auto-generate tools from the two REST endpoints above. Must
# run after those routes are defined (see openapi_tools.py's note on
# app.openapi()'s caching) and before the /mcp route below (which is hidden
# from the schema anyway -- see include_in_schema=False -- but ordering
# still wouldn't matter for it either way).
_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://mcp-lite")
for _tool in tools_from_app(app, _client):
    mcp.register(_tool)

# Pattern (b): the meta-tool, registered directly.
mcp.register(make_ask_agent_tool())

# A Resource: read-only data, not an action -- no OpenAPI operation to
# convert, so (like the meta-tool) it's registered directly.
async def _read_prompt_template() -> str:
    return REACT_PROMPT_TEMPLATE


mcp.register_resource(
    Resource(
        uri="resource://react-agent/prompt-template",
        name="ReAct prompt template",
        description="The few-shot prompt template react_agent's loop uses to steer the model's Thought/Action/Observation format.",
        mime_type="text/plain",
        read=_read_prompt_template,
    )
)


_mcp_dependencies = [Depends(verify_bearer_token), Depends(verify_origin), Depends(verify_protocol_version)]


@app.post("/mcp", include_in_schema=False, dependencies=_mcp_dependencies)
async def mcp_endpoint(
    message: dict[str, Any] | list[dict[str, Any]],
    request: Request,
    response: Response,
    mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id"),
) -> Any:
    # `initialize` is the one call allowed without an existing session --
    # it's what creates one. Everything else, including a batch, requires a
    # session already established by a prior `initialize` (see mcp.py's
    # ponytail note on why batches don't create sessions themselves).
    is_initialize = isinstance(message, dict) and message.get("method") == "initialize"
    if is_initialize:
        response.headers["Mcp-Session-Id"] = sessions.create()
    elif not sessions.valid(mcp_session_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing or invalid Mcp-Session-Id header")

    # Progress notifications only have somewhere to go if this response is
    # already committed to streaming (a client asks for that via Accept)
    # *and* told us where to address them (`_meta.progressToken`, per spec).
    # Batches are excluded on purpose -- one progress stream per HTTP
    # response, for one call, keeps this readable; see mcp.py's own
    # simplification note on batches not mixing with session/initialize
    # for the same kind of call.
    if isinstance(message, dict) and message.get("method") == "tools/call":
        params = message.get("params") or {}
        progress_token = params.get("_meta", {}).get("progressToken")
        wants_stream = "text/event-stream" in (request.headers.get("accept") or "")
        if progress_token is not None and wants_stream:
            return StreamingResponse(
                stream_tool_call_with_progress(mcp, message.get("id"), params, progress_token),
                media_type="text/event-stream",
            )

    result = await mcp.handle(message)

    if result is None:
        # All-notification call (single or batch): per spec, no body at all.
        return Response(status_code=status.HTTP_202_ACCEPTED)

    if isinstance(result, dict) and "text/event-stream" in (request.headers.get("accept") or ""):
        return sse_response(result)

    return result


@app.delete("/mcp", include_in_schema=False, dependencies=_mcp_dependencies)
async def mcp_terminate(mcp_session_id: str | None = Header(None, alias="Mcp-Session-Id")) -> Response:
    sessions.terminate(mcp_session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def demo() -> None:
    async def check_session_lifecycle_and_tools() -> Any:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # No session yet -- rejected before it ever reaches mcp.py.
            rejected = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            assert rejected.status_code == 400, rejected.text

            init = await client.post(
                "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
            )
            session_id = init.headers["Mcp-Session-Id"]
            assert session_id, "initialize must hand back a session id"
            headers = {"Mcp-Session-Id": session_id}

            listed = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
            names = {t["name"] for t in listed.json()["result"]["tools"]}
            assert {"calculator", "search", "ask_agent"} <= names, names

            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "calculator", "arguments": {"expression": "2 + 2"}},
                },
                headers=headers,
            )
            content = called.json()["result"]["content"][0]["text"]
            assert "4" in content, content
            assert called.json()["result"]["structuredContent"] == {"result": "4"}

            # SSE-framed response, when the client asks for it via Accept.
            sse = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
                headers={**headers, "Accept": "text/event-stream"},
            )
            assert sse.headers["content-type"].startswith("text/event-stream")
            assert sse.text.startswith("event: message\ndata: ")

            # An all-notification call gets 202 with no body.
            accepted = await client.post(
                "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers
            )
            assert accepted.status_code == 202
            assert accepted.text == ""

            # Resource: list, then read.
            res_list = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 5, "method": "resources/list"}, headers=headers)
            uris = {r["uri"] for r in res_list.json()["result"]["resources"]}
            assert "resource://react-agent/prompt-template" in uris

            res_read = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "resources/read",
                    "params": {"uri": "resource://react-agent/prompt-template"},
                },
                headers=headers,
            )
            assert "Thought:" in res_read.json()["result"]["contents"][0]["text"]

            # Batch: two tool calls in one POST.
            batch = await client.post(
                "/mcp",
                json=[
                    {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "calculator", "arguments": {"expression": "1 + 1"}}},
                    {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "calculator", "arguments": {"expression": "3 + 3"}}},
                ],
                headers=headers,
            )
            batch_ids = [r["id"] for r in batch.json()]
            assert batch_ids == [7, 8], batch_ids

            # Terminate, then confirm the session is really gone.
            terminated = await client.delete("/mcp", headers=headers)
            assert terminated.status_code == 204
            after_terminate = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 9, "method": "tools/list"}, headers=headers)
            assert after_terminate.status_code == 400

    asyncio.run(check_session_lifecycle_and_tools())

    async def check_progress_and_cancellation() -> None:
        # Swaps the module-level `ask_agent` tool for a scripted-LLM version
        # for the duration of this check (restored in `finally`) -- same
        # reason as elsewhere: without it this would hit the real Anthropic API.
        real_ask_agent = mcp.tools["ask_agent"]

        def parse_sse(body: str) -> list[dict[str, Any]]:
            return [json.loads(line[len("data: ") :]) for line in body.splitlines() if line.startswith("data: ")]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            init = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            headers = {"Mcp-Session-Id": init.headers["Mcp-Session-Id"]}

            # Progress: a two-step scripted run should yield at least one
            # notifications/progress event, arriving before the final
            # id-bearing response event -- not just present anywhere in the body.
            scripted = iter(
                [
                    "Thought: step one\nAction: Calculator\nAction Input: 1 + 1\n",
                    "Thought: step two\nFinal Answer: 2",
                ]
            )
            fake_llm = lambda transcript, stop=None: next(scripted)
            mcp.tools["ask_agent"] = make_ask_agent_tool(llm=fake_llm)
            try:
                resp = await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 50,
                        "method": "tools/call",
                        "params": {
                            "name": "ask_agent",
                            "arguments": {"question": "what is 1 + 1?"},
                            "_meta": {"progressToken": "tok-1"},
                        },
                    },
                    headers={**headers, "Accept": "text/event-stream"},
                )
                assert resp.headers["content-type"].startswith("text/event-stream")
                events = parse_sse(resp.text)
                progress_events = [e for e in events if e.get("method") == "notifications/progress"]
                final_events = [e for e in events if e.get("id") == 50]
                assert progress_events, events
                assert len(final_events) == 1, events
                assert final_events[0]["result"]["content"][0]["text"] == "2"
                assert events.index(progress_events[0]) < events.index(final_events[0])
            finally:
                mcp.tools["ask_agent"] = real_ask_agent

            # Cancellation: a real (short) sleep inside the worker thread
            # gives a concurrent notifications/cancelled time to land before
            # the call would finish on its own.
            def slow_fake_llm(transcript: str, stop: list[str] | None = None) -> str:
                time.sleep(0.2)
                return "Thought: done\nFinal Answer: too late"

            mcp.tools["ask_agent"] = make_ask_agent_tool(llm=slow_fake_llm)
            try:

                async def call_it() -> Any:
                    return await client.post(
                        "/mcp",
                        json={
                            "jsonrpc": "2.0",
                            "id": 51,
                            "method": "tools/call",
                            "params": {
                                "name": "ask_agent",
                                "arguments": {"question": "..."},
                                "_meta": {"progressToken": "tok-2"},
                            },
                        },
                        headers={**headers, "Accept": "text/event-stream"},
                    )

                async def cancel_it() -> None:
                    await asyncio.sleep(0.05)
                    await client.post(
                        "/mcp",
                        json={"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 51}},
                        headers=headers,
                    )

                resp, _ = await asyncio.gather(call_it(), cancel_it())
                final = next(e for e in parse_sse(resp.text) if e.get("id") == 51)
                assert final["result"]["isError"] is True
                assert final["result"]["content"][0]["text"] == "cancelled"
            finally:
                mcp.tools["ask_agent"] = real_ask_agent

    asyncio.run(check_progress_and_cancellation())

    async def check_auth() -> None:
        import os

        os.environ["MCP_LITE_TOKEN"] = "secret"
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                no_token = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
                assert no_token.status_code == 401

                with_token = await client.post(
                    "/mcp",
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                    headers={"Authorization": "Bearer secret"},
                )
                assert with_token.status_code == 200
        finally:
            del os.environ["MCP_LITE_TOKEN"]

    asyncio.run(check_auth())

    async def check_origin_and_protocol_version() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # No Origin header at all (the common case for non-browser
            # clients) must never be rejected on that basis.
            no_origin = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
            assert no_origin.status_code == 200, no_origin.text

            # An Origin header is only accepted if explicitly allowlisted;
            # MCP_LITE_ALLOWED_ORIGINS is unset here, so *any* value is denied.
            disallowed_origin = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                headers={"Origin": "https://evil.example"},
            )
            assert disallowed_origin.status_code == 403

            bad_version = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                headers={"MCP-Protocol-Version": "1999-01-01"},
            )
            assert bad_version.status_code == 400

            good_version = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                headers={"MCP-Protocol-Version": "2025-06-18"},
            )
            assert good_version.status_code == 200

    asyncio.run(check_origin_and_protocol_version())

    # Pattern (b), at the unit level with a scripted fake LLM (no network) --
    # mirrors react_agent.agent's own demo().
    scripted = iter(["Thought: done\nFinal Answer: 4"])
    fake_llm = lambda transcript, stop=None: next(scripted)
    tool = make_ask_agent_tool(llm=fake_llm)

    async def check_meta_tool() -> None:
        async def ignore_progress(progress: float, total: float | None = None, message: str | None = None) -> None:
            return None

        result = await tool.call({"question": "what is 2 + 2?"}, ignore_progress)
        assert result == "4", result

    asyncio.run(check_meta_tool())
    print("app.py: ok")


if __name__ == "__main__":
    demo()
