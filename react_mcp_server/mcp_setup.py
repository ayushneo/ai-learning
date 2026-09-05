"""FastApiMCP wiring — kept separate from main.py per the project structure."""
from fastapi import FastAPI


def mount_mcp(app: FastAPI) -> None:
    # TODO: from fastapi_mcp import FastApiMCP
    # TODO: mcp = FastApiMCP(app, name="React Tools MCP", describe_full_response_schema=True)
    # TODO: mcp.mount_http()
    ...
