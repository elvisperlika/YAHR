"""Deterministic canned jobs — the mock provider's data context (network-free).

Reused two ways: wrapped by the mock MCP server's `search` tool, and imported
directly as the search loop's offline default fetch so its self-check needs no
running server.
"""

from yahr.agents.models.job import Job


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


if __name__ == "__main__":
    import asyncio

    jobs = asyncio.run(mock_jobs("python dev"))
    assert len(jobs) == 5 and all(isinstance(j, Job) for j in jobs), jobs
    assert asyncio.run(mock_jobs("a")) != asyncio.run(mock_jobs("b")), "ids must vary"
    print("mock jobs self-check ok")
