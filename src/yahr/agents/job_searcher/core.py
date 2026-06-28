"""The Job Searcher's actual work, decoupled from the A2A protocol.

A goal-seeking loop: fetch jobs for a query (via a Provider), cache + dedupe them,
and if the goal isn't met yet, broaden the query (see refine.py) and search again
— until enough jobs are found, the refiner can no longer broaden the query
(convergence), or a round / API-call budget is hit. The executor only relays whatever this
yields, so the protocol layer never changes; the job source lives behind an MCP
server (MCPProvider), so swapping Adzuna for the mock is just a different URL.
"""

import asyncio
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, replace

from yahr.agents.models.job import Job
from yahr.agents.job_searcher.providers import MCPProvider
from yahr.agents.job_searcher.refine import refine
from yahr.config import jobs_mcp_url
from yahr.mcp.mock import mock_jobs

# A unit of work the executor relays: (text, is_final, jobs). Progress steps carry
# is_final=False and jobs=None; the single final step (is_final=True) carries the
# rendered text plus the structured jobs, which the executor ships as a data part
# so the CLI can render them as cards.
Step = tuple[str, bool, list[Job] | None]


@dataclass(frozen=True)
class Goal:
    """What the searcher is trying to reach, and the budget it may spend.

    Attributes:
        query: The starting job query.
        target: How many jobs to return: the search stops once this many distinct
            jobs are cached, and the final result is capped to it.
        max_rounds: Hard cap on search rounds (spin guard).
        max_calls: Hard cap on fetch calls (budget guard for a paid/rate-limited API).
    """

    query: str
    target: int = 5
    max_rounds: int = 3
    max_calls: int = 3


# Seams: the job source (an MCP provider's search) and the refiner, both swappable
# so the loop can be checked offline (see __main__).
Fetch = Callable[[str], Awaitable[list[Job]]]
Refiner = Callable[[str, int, int], str]

# ponytail: pull a small "find N jobs" / "top N jobs" count out of the query — a
# 1-2 digit number sitting before the word "job(s)". Word-numbers ("three"),
# years, and "positions"/"roles" are a known miss; the default target applies then.
_COUNT_RE = re.compile(r"\b(\d{1,2})\b(?=[^\d]*\bjobs?\b)", re.IGNORECASE)


def _requested_count(query: str) -> int | None:
    """The job count the query asks for (e.g. 3 in "find 3 java jobs"), or None.

    Args:
        query: The natural-language job query.
    """
    match = _COUNT_RE.search(query)
    return int(match.group(1)) if match else None


def _select_provider() -> MCPProvider:
    """The job-provider MCP server the agent talks to (its URL decides the source)."""
    return MCPProvider(jobs_mcp_url())


def _job_md(job: Job) -> str:
    """Render one job as a Markdown block, including every field it has.

    Args:
        job: The job to render. Optional fields ("" when absent) are skipped, so
            a sparse mock job (title only) renders cleanly too.
    """
    parts = [f"### {job.title}"]
    meta = " · ".join(p for p in (job.company, job.location, job.salary) if p)
    if meta:
        parts.append(f"**{meta}**")
    if job.description:
        parts.append(job.description)
    if job.url:
        parts.append(f"[Apply]({job.url})")
    return "\n\n".join(parts)


def _render(cache: dict[str, Job]) -> str:
    """Render the accumulated jobs into the task's final result (Markdown).

    The CLI renders this as Rich Markdown for a pretty display; it also stays
    readable when cached and handed to the ranker.

    Args:
        cache: The deduped jobs gathered across all rounds.
    """
    if not cache:
        return "No jobs found."
    blocks = "\n\n---\n\n".join(_job_md(job) for job in cache.values())
    return f"## {len(cache)} jobs found\n\n{blocks}"


async def _run(
    goal: Goal,
    fetch: Fetch = mock_jobs,
    refiner: Refiner = refine,
) -> AsyncIterator[Step]:
    """Drive the goal-seeking search loop, streaming progress then a final result.

    Args:
        goal: The target and budget for this search.
        fetch: The job source (an MCP provider's search; defaults to the in-process mock for tests).
        refiner: The query refiner (defaults to refine; injected in tests).

    Yields:
        (text, is_final) steps: a progress line per round, then exactly one final
        step (is_final=True) carrying the rendered result.
    """
    cache: dict[str, Job] = {}
    query, calls = goal.query, 0
    for _ in range(goal.max_rounds):
        if calls >= goal.max_calls:
            yield "Reached the API-call budget", False, None
            break
        before = len(cache)
        for job in await fetch(query):
            cache.setdefault(job.id, job)
        calls += 1
        # Report progress against the cap, not the raw page: a 20-result page for
        # a "find 3" search reads as "+3 (total 3)", matching the final result.
        was, now = min(before, goal.target), min(len(cache), goal.target)
        yield f"{query!r}: +{now - was} (total {now})", False, None
        if len(cache) >= goal.target:  # goal met
            break
        # Broaden even when this round found nothing — an empty result is the
        # strongest reason to widen. Converge only when the refiner can no
        # longer change the query (its single-token / no-op signal).
        next_query = refiner(query, len(cache), goal.target)
        if next_query == query:
            break
        query = next_query
    # Cap to the requested count (the goal's target): a single Adzuna page
    # over-fetches (20), so honour "find 3 jobs" by keeping only the first N.
    selected = dict(list(cache.items())[: goal.target])
    yield _render(selected), True, list(selected.values())


async def search(query: str) -> AsyncIterator[Step]:
    """Search for jobs matching a query, streaming progress then a final result.

    A "find N jobs" / "top N jobs" count in the query sets how many to return
    (and to search for); otherwise the default target applies.

    Args:
        query: The natural-language job query.

    Yields:
        (text, is_final) steps from the goal-seeking loop with default budget.
    """
    goal = Goal(query=query)
    if count := _requested_count(query):
        goal = replace(goal, target=count)
    async for step in _run(goal, _select_provider().search):
        yield step


if __name__ == "__main__":
    # ponytail: drive the loop offline with fake fetch/refiner to check each stop
    # condition — target reached, convergence, and the call budget (money path).
    async def _demo() -> None:
        async def fetch(q: str) -> list[Job]:
            return [Job(id=f"{q}-{i}", title=f"{q} {i}") for i in range(2)]

        def changing(q: str, found: int, target: int) -> str:
            return f"{q} x"  # always a new query -> fetch yields new jobs

        def stuck(q: str, found: int, target: int) -> str:
            return q  # never changes -> fetch repeats -> converge

        def shape(steps: list[Step]) -> bool:
            return all(not s[1] for s in steps[:-1]) and steps[-1][1]

        # Target reached: 2 new jobs/round, target 6 -> stops at 6.
        hit = [
            s async for s in _run(Goal("dev", target=6, max_rounds=10), fetch, changing)
        ]
        assert shape(hit), "stream must be progress* then one final"
        assert "6 jobs" in hit[-1][0], hit[-1][0]

        # Converged: refiner never changes the query -> stalls at 2, below target.
        conv = [
            s async for s in _run(Goal("dev", target=99, max_rounds=10), fetch, stuck)
        ]
        assert shape(conv) and "2 jobs" in conv[-1][0], conv[-1][0]

        # Empty first round must still broaden (the forli bug): the initial query
        # returns nothing, the refiner widens to one that hits.
        async def empty_first(q: str) -> list[Job]:
            return (
                [] if q == "forli" else [Job(id=f"{q}-{i}", title=q) for i in range(3)]
            )

        broadened = [
            s async for s in _run(Goal("forli", target=2), empty_first, changing)
        ]
        # Broadened (cache went 0 -> 3) then capped to the target of 2.
        assert shape(broadened) and "2 jobs" in broadened[-1][0], broadened[-1][0]

        # Budget: max_calls caps fetches regardless of target/rounds.
        cap = [
            s async for s in _run(Goal("dev", target=99, max_calls=2), fetch, changing)
        ]
        assert shape(cap) and "4 jobs" in cap[-1][0], cap[-1][0]

        # The requested count caps the result (the "find 3 jobs" bug): one Adzuna
        # page is 20, trimmed to the 3 asked for — in text and in structured jobs.
        async def twenty(q: str) -> list[Job]:
            return [Job(id=f"{q}-{i}", title=q) for i in range(20)]

        capped = [s async for s in _run(Goal("java", target=3), twenty, changing)]
        assert shape(capped) and "3 jobs" in capped[-1][0], capped[-1][0]
        assert len(capped[-1][2] or []) == 3, capped[-1][2]
        # The progress line reports against the cap too, not the raw page of 20.
        assert "+3 (total 3)" in capped[0][0] and "20" not in capped[0][0], capped[0][0]

        # _requested_count: a 1-2 digit number before "jobs" wins, else None.
        assert _requested_count("find 3 java developer jobs in milano") == 3
        assert _requested_count("top 5 python jobs") == 5
        assert _requested_count("find java jobs") is None
        assert _requested_count("java jobs over 50k") is None  # 50 is after "jobs"
        assert _requested_count("software roles in 2024") is None  # year, not a count

        # A full job renders every field; a sparse (title-only) job stays clean.
        full = _job_md(
            Job(
                "1",
                "Dev",
                company="Acme",
                location="Milano",
                description="Spring",
                url="http://x/1",
            )
        )
        assert "### Dev" in full and "**Acme · Milano**" in full
        assert "Spring" in full and "[Apply](http://x/1)" in full
        assert _job_md(Job("2", "Solo")) == "### Solo"

        # The default fetch (the in-process async mock) must actually be awaitable
        # — the loop awaits it, so a sync default would only blow up here.
        default = [s async for s in _run(Goal("dev", target=3))]
        assert shape(default) and "jobs found" in default[-1][0], default

        print("job_searcher.core self-check ok")

    asyncio.run(_demo())
