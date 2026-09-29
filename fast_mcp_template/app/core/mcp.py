"""Expose this app's own REST endpoints as MCP tools via fastapi_mcp
(github.com/tadata-org/fastapi_mcp).

# The architectural choice, stated up front
There are two different things an MCP layer over a FastAPI app can mean:
(a) expose the *individual* REST endpoints as MCP tools, and let an external
MCP client (Claude Desktop, Claude Code, an agent framework) do the
reasoning about which to call, in what order; or (b) wrap a whole internal
agent loop as one meta-tool (`ask_agent(question)`), hiding the tool-level
structure from the client entirely. This template builds (a) -- it's the
more honest use of fastapi_mcp (matching its own stated purpose: turn API
endpoints into tools, not wrap an agent), and it's what makes reasoning
observable from the outside. This exact trade-off, and the same
recommendation, is already recorded in this repo's own
`react_mcp_server/react-mcp-server-spec.md` for the hand-rolled version of
the same decision -- consistent call, independently arrived at twice.

build_mcp() is a function (not code inlined into main.py) so tests can
construct it and inspect `.tools` without booting a live MCP session.
"""
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP


def build_mcp(app: FastAPI) -> FastApiMCP:
    return FastApiMCP(
        app,
        name=app.title,
        # Full JSON-schema response descriptions make bigger, more useful
        # tool docs for the calling LLM at the cost of a larger tool list
        # payload sent on every MCP `list_tools`. Worth it until you have
        # dozens of tools; reconsider (or set per-tool) at that scale.
        describe_full_response_schema=True,
        # ponytail: excluding by name is one line; a real permissions model
        # (per-caller scopes, roles) is a separate system -- build that when
        # more than "no agent deletes anything" is actually needed.
        exclude_operations=["delete_item"],
    )


def mount_mcp(app: FastAPI) -> None:
    mcp = build_mcp(app)
    # Streamable HTTP transport (the current, non-deprecated one) at
    # POST/GET/DELETE /mcp. fastapi_mcp also has `mount_sse()` (the older
    # SSE transport, kept for clients that haven't moved off it yet) --
    # default to HTTP unless a specific client you must support needs SSE.
    mcp.mount_http()
