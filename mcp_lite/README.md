# mcp_lite

A hand-rolled MCP (Model Context Protocol) server — no `fastapi_mcp`, no the
official `mcp` SDK. Built to understand what those libraries are actually
doing underneath, the same reason `react_agent/` doesn't use LangChain: the
mechanism is the point, not the finished tool.

If you want the production version of this (tool filtering, a maintained
OpenAPI→tool converter, more spec surface handled for you), that's
[`../fast_mcp_template`](../fast_mcp_template), built on the real
`fastapi_mcp`. This project exists so you can read every line of what it's
doing for you.

## Files

| File | Purpose |
|---|---|
| `mcp.py` | The protocol core: `Tool`, `Resource`, `MCPServer` — JSON-RPC 2.0 dispatch for `initialize`, `notifications/initialized`, `tools/list`, `tools/call` (with progress reporting and cancellation), `resources/list`, `resources/read`, `ping`, plus batch requests. Transport-agnostic. |
| `openapi_tools.py` | Pattern (a): reads a FastAPI app's own OpenAPI schema and converts each operation into a `Tool`, dispatched back into the app in-process via `httpx.ASGITransport`. |
| `transport.py` | HTTP-transport concerns that sit *around* a JSON-RPC message rather than inside one: `SessionStore` (the `Mcp-Session-Id` lifecycle), `verify_bearer_token`/`verify_origin`/`verify_protocol_version` (plain `Depends()`s), `sse_response` (wraps one already-finished response as a single SSE event), `stream_tool_call_with_progress` (a genuine multi-event SSE stream: progress notifications, then the final response). |
| `app.py` | The demo: two REST endpoints (reusing `react_agent`'s calculator/search) exposed via (a); `react_agent`'s whole ReAct loop wrapped as one meta-tool via (b); `react_agent`'s prompt template exposed as a Resource. Mounts `POST /mcp` and `DELETE /mcp`. |

## (a) vs (b), and why both are here

**(a) Expose individual REST endpoints as tools.** `openapi_tools.tools_from_app()`
snapshots the app's OpenAPI schema and turns `/calculator` and `/search` into
two separately-callable MCP tools. An external MCP client does the reasoning
about which tool to call, in what order — this app doesn't decide that.

**(b) Wrap an internal agent loop as one meta-tool.** `ask_agent` isn't a
REST endpoint — there's no OpenAPI operation for `openapi_tools.py` to
convert — so it's registered directly as a hand-built `Tool` in `app.py`,
wrapping `react_agent.agent.run_agent`. From the outside it's one opaque box:
the client can't see or influence whether the agent reaches for the
calculator or search internally.

This repo already worked through this exact trade-off once, for the
`fastapi_mcp`-based version of the same idea — see
[`../react_mcp_server/react-mcp-server-spec.md`](../react_mcp_server/react-mcp-server-spec.md)
("recommendation: build (a)"). `mcp_lite` builds *both*, side by side, so the
difference is something you can call and compare rather than only read about.

## What's implemented vs. the real MCP spec (2025-06-18)

| Piece | Status | Why / how |
|---|---|---|
| JSON-RPC 2.0 envelope, `initialize`, `tools/list`, `tools/call` | Implemented | The actual mechanism every MCP client depends on. |
| `notifications/initialized` (no response) | Implemented | Cheap, and getting it wrong (replying to a notification) is a real protocol bug worth seeing once. |
| Resources (`resources/list`, `resources/read`) | Implemented | A genuinely different capability from a tool — read-only, URI-addressed data, no side effect. `app.py` exposes `react_agent`'s prompt template as one; `initialize`'s advertised `capabilities` only includes `resources` when at least one is registered. |
| Batch requests (a JSON array of messages in one POST) | Implemented | `MCPServer.handle()` accepts a single message or a list; an all-notification batch correctly produces no response at all, same rule as a single notification. Simplification: a batch can't contain the `initialize` call that establishes a session — see the `ponytail:` note in `mcp.py`. |
| Session lifecycle (`Mcp-Session-Id`) | Implemented | `transport.py`'s `SessionStore`: `initialize` mints an id returned via response header; every later call must echo it or gets `400`; `DELETE /mcp` ends it. In-memory only — a `ponytail:` comment in `transport.py` names the ceiling (single process, not shared across workers). |
| SSE-framed responses | Implemented, two forms | Most calls: `Accept: text/event-stream` on `POST /mcp` gets the JSON-RPC response wrapped as one SSE `data:` event (`transport.py::sse_response`). A `tools/call` with a `_meta.progressToken` gets a genuine multi-event stream instead — see the progress row below. What's still missing: `GET /mcp` for a stream that outlives any single request (this project has no source of messages that originate outside a request-response cycle -- no subscriptions, no sampling -- so there's nothing to push through one). |
| Auth (bearer token) | Implemented | `transport.py::verify_bearer_token` — a plain FastAPI `Depends()` on the `/mcp` routes, opt-in via the `MCP_LITE_TOKEN` env var. This *is* the idea behind `fastapi_mcp`'s `AuthConfig(dependencies=[...])`: bridge onto FastAPI's own DI rather than a parallel mechanism. Enough for clients where you configure the token directly — Claude Code (`claude mcp add --transport http <url> --header "Authorization: Bearer ..."`) and OpenAI's Responses API `mcp` tool (its `headers` field). **Not** enough for Claude.ai's web "Custom Connector" UI, which requires a real OAuth 2.1 flow (dynamic client registration, protected-resource metadata, PKCE) — not implemented; see below. |
| `ping` | Implemented | Trivial (`{}` back), but real clients and proxies use it as a liveness check. |
| `structuredContent` on tool results, `json.dumps` instead of `str()` | Implemented | `str()` on a dict result produced Python repr syntax (`{'a': 1}`), not valid JSON — a real bug, not a spec gap, fixed regardless of the rest of this table. `structuredContent` (2025-06-18 addition) additionally hands a dict result back as real JSON, not just JSON-shaped text. |
| Tool `annotations` (`readOnlyHint`, `idempotentHint`, ...) | Implemented | `openapi_tools.py` derives `readOnlyHint` from the HTTP method (GET → likely read-only, POST → not) as a default, not a guarantee; `app.py` sets `ask_agent`'s by hand since it's neither read-only nor idempotent. |
| `MCP-Protocol-Version` request header | Implemented | Permissive when absent (older clients predate this header); rejects a version this server doesn't understand when present. |
| `Origin` header validation | Implemented | Spec-mandated DNS-rebinding protection. Deny-by-default: any request carrying an `Origin` header must be explicitly allowlisted via `MCP_LITE_ALLOWED_ORIGINS`; requests with no `Origin` at all (true of most non-browser MCP clients) are unaffected. |
| CORS with `Mcp-Session-Id` exposed | Implemented | Only relevant to browser-based clients (Claude.ai web, ChatGPT web) — without `expose_headers`, a browser can receive the session header on the wire and still be unable to read it from JS. Only enabled when `MCP_LITE_ALLOWED_ORIGINS` is set. |
| Progress notifications (`notifications/progress`) | Implemented, streaming-only | `transport.py::stream_tool_call_with_progress` turns one `tools/call` into a real multi-event SSE stream when the client sends `Accept: text/event-stream` *and* a `_meta.progressToken` — plain single-JSON-response calls have no room to carry an interim message at all, so progress is silently absent there rather than attempted. `app.py`'s `ask_agent` reports one event per ReAct loop iteration; `run_agent` gained an optional `on_step` callback (in `react_agent/agent.py`, backward-compatible) to make that possible, bridged from its worker thread to the event loop via `asyncio.run_coroutine_threadsafe`. |
| Request cancellation (`notifications/cancelled`) | Implemented, with an honest limit | `MCPServer` tracks each `tools/call` as a real `asyncio.Task` keyed by request id; a `notifications/cancelled` (arriving on any concurrent request, since it's just another POST) cancels that task and the original call gets back a clean `"cancelled"` result instead of a broken connection. The limit: `ask_agent`'s call is a sync `run_agent` running via `asyncio.to_thread` — cancelling the *asyncio* task stops the server from waiting on it, but the underlying OS thread has no way to be interrupted and keeps running `run_agent` to completion in the background regardless, its result just discarded. True interruption would need `run_agent` itself to check a cancellation flag between loop iterations — not implemented, since it isn't currently expensive enough (LLM calls only, no long tool executions) to be worth that + it only fully matters for `ask_agent`, not the REST-endpoint tools which return almost immediately anyway. |
| OAuth 2.1 (dynamic client registration, protected-resource metadata, PKCE) | Not implemented | The one remaining item that would actually be a separate subsystem — an authorization server, not a header check. Needed only if the specific target is Claude.ai's web Custom Connector UI; Claude Code and OpenAI's Responses API both accept a static bearer token instead (see the Auth row above). |
| Prompts, Sampling, Roots, Elicitation, Subscriptions | Not implemented | Separate protocol capabilities again; none change what "a tool call" or "a resource read" fundamentally is, which is what this project is for. |
| Path params / headers / file uploads in `openapi_tools.py` | Not implemented | Only GET-with-query-params and POST-with-JSON-body are converted; the two demo endpoints don't need more, and `_build_tool` says where to extend it. |

## If your target is Claude.ai's web Custom Connector, not Claude Code/API or OpenAI

That's the one case the table above flags as a real gap: Claude.ai's web UI for adding a remote MCP server requires OAuth, and won't accept a manually-configured static token the way Claude Code and OpenAI's Responses API do. Building that (an authorization server: `/register`, `/authorize`, `/token`, `/.well-known/oauth-protected-resource`) is a substantially bigger, separate piece of work — closer in scope to a new project than an addition to this one. Not built here; ask if that's actually the target before it's worth doing.

## Verification checkpoints

1. `python -m mcp_lite.mcp` — the protocol core in isolation: a normal tool
   call, a tool that raises (must come back as `isError: true` inside a
   *successful* JSON-RPC response, not a JSON-RPC error), an unknown
   method/tool (must be a JSON-RPC error), a notification (must get `None`),
   a resource list/read (including an unknown-uri error), a batch of mixed
   requests+notifications (only the requests get responses, in order; an
   all-notification batch gets `None` too), a tool that reports progress via
   `call_tool()` directly (events arrive in order, before the result), and
   cancellation (a `forever`-running tool, cancelled mid-flight via
   `notifications/cancelled`, comes back as a clean `"cancelled"` result —
   plus cancelling an unknown/already-finished id is confirmed to be a
   silent no-op, not an error).
2. `python -m mcp_lite.app` — end to end over the real ASGI app: a call
   before `initialize` is rejected with `400`; `initialize` hands back a
   session id via the `Mcp-Session-Id` response header; `tools/list` with
   that header returns `calculator`, `search`, and `ask_agent`; `tools/call`
   on `calculator` round-trips through the actual `/calculator` REST
   endpoint (not a mock) *and* comes back with valid-JSON text plus
   `structuredContent`; asking for `Accept: text/event-stream` gets an
   SSE-framed response; a batch of two `tools/call`s gets two responses in
   order; `DELETE /mcp` ends the session and a call afterward is rejected
   again; setting `MCP_LITE_TOKEN` makes an unauthenticated call `401` and a
   correctly-authenticated one succeed; a disallowed `Origin` header gets
   `403` while no `Origin` header at all is unaffected; an unrecognized
   `MCP-Protocol-Version` gets `400`; a real streamed `ask_agent` call (with
   a scripted fake LLM) produces progress events strictly before its final
   response; and a slow streamed `ask_agent` call, raced against a
   concurrent `notifications/cancelled` for the same request id via
   `asyncio.gather`, comes back cancelled. The meta-tool is also checked at
   the unit level with a scripted fake LLM (same pattern as
   `react_agent.agent`'s own `demo()`), so none of this needs a network call
   or an API key to run.
3. `python -m react_agent.agent --demo` — confirms `run_agent`'s new
   `on_step` callback still fires exactly once per loop iteration with the
   expected status strings, and that everything else about the loop is
   unchanged (this parameter is purely additive/optional).
4. Point a real MCP client at `http://127.0.0.1:8000/mcp` (after `fastapi dev
   mcp_lite/app.py`) and confirm it lists the same three tools and one
   resource — the thing the checks above can't prove: that the wire format
   is actually correct for a real client, not just for this repo's own test
   client.

## Quick start

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...           # only needed for a real (non-demo) ask_agent call
export MCP_LITE_TOKEN=...              # optional -- requires a bearer token on /mcp if set
export MCP_LITE_ALLOWED_ORIGINS=...    # optional, comma-separated -- only needed for a browser-based client
python -m mcp_lite.mcp                  # self-check: protocol core
python -m mcp_lite.app                  # self-check: sessions, auth, origin/version headers, SSE, batch, resources, both patterns
fastapi dev mcp_lite/app.py             # run for real
```

For Claude Code: `claude mcp add --transport http mcp-lite http://127.0.0.1:8000/mcp` (add `--header "Authorization: Bearer $MCP_LITE_TOKEN"` if set). For OpenAI's Responses API, use the `mcp` tool type pointed at the same URL, with `headers` set the same way.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-14 | Built from scratch after reading `fastapi_mcp`'s source (not its library) — hand-rolled JSON-RPC core, OpenAPI→tool conversion, and both the (a) individual-endpoints and (b) meta-tool patterns, reusing `react_agent`'s tools/loop for the demo | Ayush Sood |
| 2026-09-14 | Added the four features named as skipped in the first pass: Resources, session lifecycle (`Mcp-Session-Id`), SSE-framed responses, bearer-token auth, and JSON-RPC batch requests. New `transport.py` holds the HTTP-transport pieces (sessions/auth/SSE) separately from the JSON-RPC core in `mcp.py` | Ayush Sood |
| 2026-09-14 | Interop pass for real Claude/OpenAI clients: fixed a real bug (`str()` on a dict tool result produced invalid-JSON Python repr text), added `structuredContent`, tool `annotations`, `ping`, `MCP-Protocol-Version` and `Origin` header validation, and CORS with `Mcp-Session-Id` exposed. Explicitly did not build OAuth (needed only for Claude.ai's web Custom Connector UI) or cancellation/progress (blocked on `asyncio.to_thread` not being forcibly cancellable) — named as the two remaining real gaps rather than silently skipped | Ayush Sood |
| 2026-09-14 | Added progress notifications and cancellation (user asked for both, explicitly declined OAuth for now). `MCPServer.call_tool` tracks each call as a real `asyncio.Task`; `notifications/cancelled` cancels it from a concurrent request; `transport.py::stream_tool_call_with_progress` turns a `tools/call` into a genuine multi-event SSE stream when a client asks for one. `react_agent.agent.run_agent` gained an optional, backward-compatible `on_step` callback so `ask_agent` has something to report progress from. Documented the real limit honestly: cancelling the asyncio task can't interrupt the underlying OS thread `run_agent` runs in | Ayush Sood |
