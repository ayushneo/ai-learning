"""One check that the MCP tool surface is what app/core/mcp.py claims it is,
without needing a live MCP session/handshake -- build_mcp() returns the
FastApiMCP instance with `.tools` already computed from the app's OpenAPI
schema, so this just inspects it directly.
"""
from app.core.mcp import build_mcp
from app.main import app


def test_exposed_tools_match_operation_ids() -> None:
    mcp = build_mcp(app)
    names = {tool.name for tool in mcp.tools}

    assert {"create_item", "get_item", "list_items"} <= names
    assert "delete_item" not in names, "destructive endpoint must stay excluded by default"
