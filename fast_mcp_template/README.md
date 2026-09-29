# fast_mcp_template

Same layered CRUD/Docker/Poetry base as [`fastapi_template`](../fastapi_template),
plus one thing: the app's own REST endpoints are exposed as MCP tools via
[`fastapi_mcp`](https://github.com/tadata-org/fastapi_mcp), so an MCP client
(Claude Desktop, Claude Code, any agent framework) can call them directly.
Copy this directory to start a real project; delete `items` once you've read
how the wiring works.

Built by reading the actual `fastapi_mcp` source (its README's own code
sample is thinner than what's needed to get filtering/auth/transport right),
not from the surveyed blog posts — see "What was actually useful" below for
why most of those added nothing beyond `fastapi_mcp`'s own docs.

## File structure

Identical to `fastapi_template/` (see that README for the full layout and its
own trade-offs table — those still apply here) plus:

```
fast_mcp_template/
├── app/
│   ├── core/
│   │   └── mcp.py          -- NEW: builds + mounts the MCP server over this app's own routes
│   ├── api/v1/
│   │   └── items.py         -- CHANGED: explicit operation_id on every route (see why below)
│   └── schemas/
│       └── item.py           -- CHANGED: Field(..., description=...) on every field
└── tests/
    └── test_mcp.py             -- NEW: asserts the exposed tool set, no live MCP session needed
```

## The one architectural choice that matters here

There are two different things "add MCP to a FastAPI app" can mean:

**(a) Expose the individual REST endpoints as MCP tools** and let an external
MCP client do the reasoning about which to call, in what order — this is
what `fastapi_mcp` is actually built for (turn API endpoints into tools,
not wrap an agent), and what this template does.

**(b) Wrap an internal agent loop as one meta-tool** (`ask_agent(question)`
that reasons internally and returns a final answer) — simpler to wire, but
hides all tool-selection structure from the client; from the outside it's
one opaque tool.

This template builds (a). Notably, this repo already made and recorded the
exact same call independently, for the hand-rolled (non-`fastapi_mcp`)
version of this same decision, in `react_mcp_server/react-mcp-server-spec.md`
— same reasoning, arrived at twice without cross-referencing.

## Trade-offs specific to the MCP layer

(General FastAPI trade-offs — models vs. schemas, error handling, pagination,
logging — are the same as `fastapi_template` and not repeated here.)

| Decision | Options | Chosen, and why |
|---|---|---|
| `operation_id` | Auto-generated (function name + path hash) vs. explicit on every route | Explicit, always — `fastapi_mcp` uses `operation_id` as the MCP tool's *name*. Leave it auto and an unrelated refactor (renaming the function, moving the router) silently renames or breaks the tool from an agent's perspective. The single most-repeated warning across every `fastapi_mcp` write-up surveyed. |
| Tool descriptions | Minimal vs. `Field(..., description=...)` on every schema field | Detailed — this is the *entire* quality signal an MCP client (an LLM) has to decide whether/how to call a tool. There's no separate "tool doc" to write; the Pydantic field description *is* the doc. |
| Transport | `mount_sse()` (legacy Server-Sent Events) vs. `mount_http()` (Streamable HTTP) | HTTP — the current, non-deprecated transport (verified against `fastapi_mcp`'s own source, not just its README). Use SSE only if a specific client you must support hasn't moved off it. |
| Exposure surface | Expose every endpoint vs. filter | Filtered — `delete_item` is excluded via `exclude_operations` in `app/core/mcp.py` by default. A destructive endpoint has a bigger blast radius when the caller is an LLM deciding on its own when to invoke it than when it's a human confirming a dialog. Still a normal REST endpoint either way; re-include it explicitly once you actually want that. |
| Auth | Build a custom auth bridge vs. `fastapi_mcp`'s `AuthConfig(dependencies=[Depends(...)])` | Not wired by default (no auth in this template at all, same as `fastapi_template`) — but when you add it, pass your existing `Depends()` into `AuthConfig` rather than writing a separate MCP-specific auth path. `fastapi_mcp`'s whole pitch over a generic OpenAPI→MCP converter is reusing FastAPI's own dependencies for this. |
| Where to build the MCP object | Inline in `main.py` vs. a `build_mcp()` function | A function (`app/core/mcp.py`) — lets `tests/test_mcp.py` inspect `.tools` directly without booting a live MCP session/handshake. |

## What was actually useful from the surveyed sources

| Source | Verdict |
|---|---|
| [tadata-org/fastapi_mcp](https://github.com/tadata-org/fastapi_mcp) (source, not just README) | The only one worth reading closely — this template's `mount_http()`/`exclude_operations`/`AuthConfig` usage all came from reading `fastapi_mcp/server.py` directly, because **the README's own basic example (`mcp.mount()`) already calls a soft-deprecated path** — worth knowing before copying it verbatim from the README. |
| `react_mcp_server/react-mcp-server-spec.md` (this repo, already existed) | Same "(a) not (b)" call, same `operation_id`/`Field(description=...)` warnings — written independently before this template, confirms the pattern rather than introducing it. |
| modelcontextprotocol/servers | Reference *server* implementations (stdio-based tool servers), not FastAPI-specific — no additional guidance for this template's actual problem (exposing an existing HTTP API), so nothing was taken from it directly. |
| The Medium/blog posts (Ruchi Awasthi, uselessai.in, Jayant Nehra) and mintmcp's blog | General MCP-concept explainers, largely restating what `fastapi_mcp`'s own README already says, at a lower technical resolution. mcpservers.org is a directory listing, not a guide. None added anything beyond what's already reflected above — surveyed, not skipped out of laziness. |

## A live upstream bug, verified 2026-09-13

`fastapi-mcp==0.4.0` (latest on PyPI) calls the `mcp` SDK's `Server(name, description)`
positionally; `mcp>=2.0.0` made `description` keyword-only, so the combination
raises `TypeError` at import time. `pyproject.toml` pins `mcp = "<2.0"` to work
around it. Re-check this pin when bumping `fastapi-mcp` — the fix is on the
`fastapi_mcp` side, not something to route around with more code here.

## Quick start

```bash
cp .env.example .env
poetry install
make migrate
make dev        # fastapi dev app/main.py -- REST at /v1/items, docs at /docs, MCP at /mcp
make test       # includes tests/test_mcp.py
```

Point an MCP client (e.g. Claude Desktop's config, or `mcp-remote`) at
`http://127.0.0.1:8000/mcp` and confirm it lists `create_item`, `get_item`,
`list_items`, and `health` — but not `delete_item`.

## Extending this template

Same as `fastapi_template` for adding a new resource (model → schema →
repository → service → route → one line in `router.py`) — the only addition
is: give the route an explicit `operation_id`, and write its schema field
descriptions for an LLM reader. It becomes an MCP tool automatically the
next time `build_mcp()` runs; no separate registration step.

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-09-13 | Forked from `fastapi_template`; added `fastapi_mcp` wiring, explicit `operation_id`s, tool-facing field descriptions, and the exposure-filtering example | Ayush Sood |
