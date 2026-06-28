"""The mock MCP server: the same `search` tool as Adzuna, canned and offline.

Thin wiring — adapts mock_jobs() (in jobs.py) into the provider-agnostic
``search(query) -> {"jobs": [...]}`` MCP tool, so the whole pipeline can run
end-to-end over MCP without credentials.
"""

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from yahr.agents.roster import MOCK_MCP_ADDRESS
from yahr.mcp.mock.jobs import mock_jobs

mcp = FastMCP("yahr-mock", host=MOCK_MCP_ADDRESS.ip, port=MOCK_MCP_ADDRESS.port)


@mcp.tool()
async def search(query: str) -> dict[str, Any]:
    """Return canned jobs matching a query, mirroring the Adzuna tool's shape.

    Args:
        query: The job query to search for.

    Returns:
        A {"jobs": [...]} dict; each job carries the Job dataclass fields.
    """
    return {"jobs": [asdict(j) for j in await mock_jobs(query)]}


def serve() -> None:
    """Run the mock provider as an MCP server over streamable-http until interrupted."""
    mcp.run(transport="streamable-http")
