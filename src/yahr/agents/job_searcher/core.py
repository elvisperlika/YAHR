"""The Job Searcher's actual work, decoupled from the A2A protocol.

A goal-seeking loop: fetch jobs for a query (via a Provider), cache + dedupe them,
and if the goal isn't met yet, broaden the query (see refine.py) and search again
— until enough jobs are found, the refiner can no longer broaden the query
(convergence), or a round / API-call budget is hit. The executor only relays whatever this
yields, so the protocol layer never changes; the job source lives behind the
Provider interface, so swapping Adzuna for the mock changes nothing here.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

from yahr.agents.models.job import Job
from yahr.agents.job_searcher.providers import Adzuna, MockProvider, Provider
from yahr.agents.job_searcher.refine import refine

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
        target: Stop once this many distinct jobs are cached.
        max_rounds: Hard cap on search rounds (spin guard).
        max_calls: Hard cap on fetch calls (budget guard for a paid/rate-limited API).
    """

    query: str
    target: int = 10
    max_rounds: int = 3
    max_calls: int = 3


# Seams: the job source (a Provider's search) and the refiner, both swappable so
# the loop can be checked offline (see __main__).
Fetch = Callable[[str], Awaitable[list[Job]]]
Refiner = Callable[[str, int, int], str]


def _select_provider() -> Provider:
    """The real provider when its credentials are set, else the offline mock."""
    try:
        return Adzuna.from_env()
    except Exception:
        return MockProvider()


def _job_md(job: Job) -> str:
    """Render one job as a Markdown block, including every field it has.

    Args:
        job: The job to render. Optional fields ("" when absent) are skipped, so
            a sparse mock job (title only) renders cleanly too.
    """
    parts = [f"### {job.title}"]
    meta = " · ".join(p for p in (job.company, job.location) if p)
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
    fetch: Fetch = MockProvider().search,
    refiner: Refiner = refine,
) -> AsyncIterator[Step]:
    """Drive the goal-seeking search loop, streaming progress then a final result.

    Args:
        goal: The target and budget for this search.
        fetch: The job source (a Provider's search; defaults to the mock, injected in tests).
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
        yield f"{query!r}: +{len(cache) - before} (total {len(cache)})", False, None
        if len(cache) >= goal.target:  # goal met
            break
        # Broaden even when this round found nothing — an empty result is the
        # strongest reason to widen. Converge only when the refiner can no
        # longer change the query (its single-token / no-op signal).
        next_query = refiner(query, len(cache), goal.target)
        if next_query == query:
            break
        query = next_query
    yield _render(cache), True, list(cache.values())


async def search(query: str) -> AsyncIterator[Step]:
    """Search for jobs matching a query, streaming progress then a final result.

    Args:
        query: The natural-language job query.

    Yields:
        (text, is_final) steps from the goal-seeking loop with default budget.
    """
    async for step in _run(Goal(query=query), _select_provider().search):
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
        assert shape(broadened) and "3 jobs" in broadened[-1][0], broadened[-1][0]

        # Budget: max_calls caps fetches regardless of target/rounds.
        cap = [
            s async for s in _run(Goal("dev", target=99, max_calls=2), fetch, changing)
        ]
        assert shape(cap) and "4 jobs" in cap[-1][0], cap[-1][0]

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

        print("job_searcher.core self-check ok")

    asyncio.run(_demo())
