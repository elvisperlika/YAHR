"""Fetch a job's full description from its link, cleaned to just the posting.

Adzuna's /search response carries only a truncated ``description`` (a few hundred
chars ending in "…"); the full posting lives at the redirect_url, already stored
as ``Job.url``. This fetches that page via markitdown (already a dep), then runs
one LLM pass to keep only the job description as well-formatted Markdown —
dropping the site nav, cookie/ad banners, "apply"/"share" chrome and footer that
scraping a whole page drags in. Best-effort and concurrent: any failure (timeout,
a bot-blocked or JS-only page, the LLM down) falls back to the raw page text and
then to the truncated description, so search never breaks.
"""

import asyncio
from dataclasses import replace
from typing import cast

import requests
from markitdown import MarkItDown
from rich.console import Console

from yahr.agents.models.job import Job
from yahr.config import openrouter_client

console = Console()

# ponytail: requests' default User-Agent ("python-requests/…") gets 403'd by
# Adzuna's redirect/land pages and many employer sites — a browser UA clears most
# of them. markitdown is sync (requests under the hood), so each fetch runs in a
# thread and they all go concurrently via gather.
_session = requests.Session()
_session.headers["User-Agent"] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_md = MarkItDown(requests_session=_session)

# ponytail: per-job ceiling (fetch + one LLM pass) so one slow posting can't
# stall the whole search. The to_thread keeps running after a timeout (asyncio
# can't cancel it); its result is just discarded — fine at this scale.
_TIMEOUT = 30.0

# ponytail: bound concurrent enrichments so 20 results don't fire 20 LLM calls at
# once and trip the free model's rate limit. Raise it if throughput matters.
_SEM = asyncio.Semaphore(5)

_CLEAN_SYSTEM = (
    "You are given the raw Markdown of a web page scraped whole, containing a "
    "single job posting plus surrounding clutter (site navigation, menus, "
    "cookie/ad banners, 'apply'/'share'/'save' buttons, related-jobs lists, "
    "footer links). Return ONLY the job posting itself as clean, well-formatted "
    "GitHub-flavored Markdown: keep the role, responsibilities, requirements, "
    "skills, and benefits with sensible headings and bullet lists; drop "
    "everything that is not part of the posting. Use ONLY the text present — "
    "never invent, summarize away, or translate anything. Output only the "
    "Markdown, no preamble, no code fences."
)


def _clean(raw: str) -> str:
    """Reduce a whole scraped page to just the job description via one LLM pass.

    Args:
        raw: The full page text markitdown extracted.

    Returns:
        The job description as clean Markdown, or "" on any LLM/parse failure
        (the caller falls back to the raw text).
    """
    try:
        # ponytail: sync LLM call (matches convert.py) run inside a thread by the
        # caller; the OpenAI client carries its own timeout.
        client, model = openrouter_client()
        reply = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _CLEAN_SYSTEM},
                {"role": "user", "content": raw},
            ],
        )
        return (reply.choices[0].message.content or "").strip()
    except Exception:
        # ponytail: any LLM failure -> caller keeps the raw extracted text.
        return ""


def _fetch_and_clean(job: Job) -> str:
    """Fetch ``job.url`` and return its description as clean Markdown.

    markitdown extracts the whole page text; :func:`_clean` then keeps only the
    posting. Falls back to the raw extracted text if the LLM pass yields nothing.

    Args:
        job: The job whose url to fetch (assumed non-empty).
    """
    raw = (_md.convert(job.url).text_content or "").strip()
    if not raw:
        return ""
    return _clean(raw) or raw


async def _full_description(job: Job) -> Job:
    """Return ``job`` with its description replaced by the full, cleaned posting.

    On no url, any failure, or an empty result, returns the job unchanged (its
    truncated description is the floor).

    Args:
        job: The job to enrich.
    """
    if not job.url:
        return job
    try:
        async with _SEM:
            text = await asyncio.wait_for(
                asyncio.to_thread(_fetch_and_clean, job), _TIMEOUT
            )
        return replace(job, description=text) if text else job
    except Exception as exc:
        # ponytail: best-effort — log and keep the truncated description.
        console.log(f"  [yellow]enrich skipped[/] {job.url}: {exc}")
        return job


async def with_full_descriptions(jobs: list[Job]) -> list[Job]:
    """Enrich every job's description from its link, concurrently.

    Args:
        jobs: The jobs parsed from the search response.

    Returns:
        The jobs in the same order, each with its full, cleaned description where
        one could be fetched (truncated description kept otherwise).
    """
    return await asyncio.gather(*(_full_description(j) for j in jobs))


if __name__ == "__main__":
    # ponytail: check the enrich rules with the fetch and the LLM both faked —
    # no url is left alone; a good fetch + clean replaces the snippet (other
    # fields kept); a failed clean falls back to the raw page text; an empty
    # fetch and a raising fetch fall back to the truncated original. The live
    # HTTP/markitdown/LLM path is left to a real run.
    from types import SimpleNamespace

    base = Job("1", "Dev", description="truncated…", url="http://x/1")

    class FakeMD:
        def __init__(self, text: str | None = None, boom: bool = False) -> None:
            self._text, self._boom = text, boom

        def convert(self, _: str) -> SimpleNamespace:
            if self._boom:
                raise RuntimeError("blocked")
            return SimpleNamespace(text_content=self._text)

    async def _demo() -> None:
        global _md, _clean

        # No url -> untouched, nothing fetched.
        nodesc = Job("2", "Solo")
        assert (await with_full_descriptions([nodesc]))[0] is nodesc

        # Good fetch + good clean -> cleaned description, other fields preserved.
        _md = cast("MarkItDown", FakeMD("nav … JOB BODY: Spring, JPA … footer"))
        _clean = lambda raw: "## Role\n\n- Spring\n- JPA"  # noqa: ARG005, E731
        out = (await with_full_descriptions([base]))[0]
        assert out.description == "## Role\n\n- Spring\n- JPA", out
        assert out.id == "1" and out.url == base.url, out

        # Clean yields nothing (LLM down) -> fall back to raw extracted text.
        _clean = lambda raw: ""  # noqa: ARG005, E731
        out = (await with_full_descriptions([base]))[0]
        assert out.description == "nav … JOB BODY: Spring, JPA … footer", out

        # Empty fetch -> keep the truncated original.
        _md = cast("MarkItDown", FakeMD("   "))
        assert (await with_full_descriptions([base]))[0].description == "truncated…"

        # Fetch raises -> keep the truncated original (best-effort floor).
        _md = cast("MarkItDown", FakeMD(boom=True))
        assert (await with_full_descriptions([base]))[0].description == "truncated…"

    asyncio.run(_demo())
    print("adzuna enrich self-check ok")
