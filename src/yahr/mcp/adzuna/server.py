"""The Adzuna MCP server: exposes the generic `search` tool over streamable-http.

Thin wiring — it adapts search_adzuna() (Adzuna HTTP, in client.py) into the
provider-agnostic ``search(query) -> {"jobs": [...]}`` MCP tool the Job Searcher
agent calls. All Adzuna specifics live in client.py / extract.py, not here.
"""

from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from yahr.agents.roster import ADZUNA_MCP_ADDRESS
from yahr.mcp.adzuna.client import search_adzuna

mcp = FastMCP("yahr-adzuna", host=ADZUNA_MCP_ADDRESS.ip, port=ADZUNA_MCP_ADDRESS.port)


@mcp.tool()
async def search(query: str) -> dict[str, Any]:
    """Search Adzuna for jobs matching a natural-language query.

    Args:
        query: The natural-language job query (e.g. "java jobs in milano with salary").

    Returns:
        A {"jobs": [...]} dict; each job carries the Job dataclass fields.
    """
    return {"jobs": [asdict(j) for j in await search_adzuna(query)]}


def serve() -> None:
    """Run the Adzuna provider as an MCP server over streamable-http until interrupted."""
    mcp.run(transport="streamable-http")
