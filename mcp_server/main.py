from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.clients.orchestrator_client import OrchestratorClient
from mcp_server.transport.tools import register_tools


def create_app() -> FastMCP:
    mcp = FastMCP("job-bot-mcp")
    client = OrchestratorClient()
    register_tools(mcp, client)
    return mcp


mcp = create_app()


if __name__ == "__main__":
    mcp.run(transport="stdio")