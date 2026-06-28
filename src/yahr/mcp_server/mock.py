"""A deterministic job provider as an MCP server — for offline runs and tests.

Same generic `search(query)` tool as the Adzuna server, but canned and
network-free, so the whole pipeline can run end-to-end over MCP without
credentials. `mock_jobs` stays importable directly so the search loop's offline
self-check (its default fetch) doesn't need a live server.
"""

import asyncio
from dataclasses import asdict
from typing import Any

from mcp.server.fastmcp import FastMCP

from yahr.agents.models.job import Job
from yahr.agents.roster import MOCK_MCP_ADDRESS


async def mock_jobs(query: str) -> list[Job]:
    """Return five deterministic jobs keyed by the query.

    Async to match the search loop's Fetch seam (it ``await``s the job source),
    so this can stand in for a real provider's ``search`` as the offline default.

    Args:
        query: The job query to search for.

    Returns:
        Jobs whose ids vary with the query, so a refined query surfaces new ones
        the search loop's cache hasn't seen.
    """
    base = abs(hash(query))
    return [Job(id=f"{base}-{i}", title=f"{query.title()} #{i}") for i in range(5)]


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


if __name__ == "__main__":
    jobs = asyncio.run(mock_jobs("python dev"))
    assert len(jobs) == 5 and all(isinstance(j, Job) for j in jobs), jobs
    assert asyncio.run(mock_jobs("a")) != asyncio.run(mock_jobs("b")), "ids must vary"
    print("mock mcp server self-check ok")
