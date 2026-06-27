"""The Job Searcher's actual work, decoupled from the A2A protocol.

ponytail: still a mock (sleeps + canned text); swap the body of search() for the
real Adzuna/LLM call when the agent is built. The executor only relays whatever
this yields, so the protocol layer never changes when the real search lands.
"""

import asyncio
from collections.abc import AsyncIterator

# A unit of work the executor relays: (text, is_final). Progress steps carry
# is_final=False; the single final step (is_final=True) is the task result.
Step = tuple[str, bool]


async def search(query: str) -> AsyncIterator[Step]:
    """Search for jobs matching a query, streaming progress then a final result.

    Args:
        query: The natural-language job query.

    Yields:
        (text, is_final) steps: progress lines while working, then exactly one
        final step (is_final=True) carrying the result.
    """
    for step in (f"Querying job board for {query!r}", "Enriching the listings found"):
        await asyncio.sleep(0.7)
        yield step, False
    await asyncio.sleep(0.7)
    yield f"[Job Searcher mock] Would search jobs for: {query!r}", True


if __name__ == "__main__":
    # ponytail: assert the stream shape the executor depends on — N progress
    # steps then exactly one final step.
    async def _demo() -> None:
        steps = [s async for s in search("python dev")]
        assert all(not s[1] for s in steps[:-1]), "only the last step may be final"
        assert steps[-1][1], "stream must end with a final step"
        print("job_searcher.core self-check ok")

    asyncio.run(_demo())
