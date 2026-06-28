"""Job providers behind one interface, so the search loop never knows the source.

`Provider` is the interface the Job Searcher depends on. `Adzuna` is the real
implementation — it encapsulates its credentials and HTTP, exposing only
`search(query)`. `MockProvider` serves canned jobs for offline runs and tests.
Swapping providers changes nothing in core.py.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx
from rich.console import Console

from yahr.agents.models.job import Job
from yahr.config import load_dotenv, openrouter_client

# ponytail: same server-side log as the executor/refiner — shows the structured
# query Adzuna actually receives (never the app_id/key).
console = Console()


class Provider(ABC):
    """A source of job postings: the only job-board surface the loop depends on."""

    @abstractmethod
    async def search(self, query: str) -> list[Job]:
        """Return jobs matching the query.

        Args:
            query: The job query to search for.
        """
        ...


class MockProvider(Provider):
    """Deterministic canned jobs — for offline runs and tests, no network."""

    async def search(self, query: str) -> list[Job]:
        """Return five deterministic jobs keyed by the query.

        Args:
            query: The job query to search for.

        Returns:
            Jobs whose ids vary with the query, so a refined query surfaces new
            ones the cache hasn't seen.
        """
        base = abs(hash(query))
        return [Job(id=f"{base}-{i}", title=f"{query.title()} #{i}") for i in range(5)]


class Adzuna(Provider):
    """The Adzuna job board, encapsulating its credentials and HTTP access.

    Callers see only `search`; the app id/key, country, and endpoint stay private.
    """

    _BASE = "https://api.adzuna.com/v1/api/jobs"

    def __init__(
        self, app_id: str, app_key: str, country: str = "it", per_page: int = 20
    ) -> None:
        """Bind credentials and search scope.

        Args:
            app_id: Adzuna application id.
            app_key: Adzuna application key.
            country: Two-letter Adzuna country code (e.g. 'it', 'gb').
            per_page: Results requested per page.
        """
        self._app_id = app_id
        self._app_key = app_key
        self._country = country
        self._per_page = per_page

    @classmethod
    def from_env(cls) -> "Adzuna":
        """Build from ADZUNA_APP_ID / ADZUNA_APP_KEY / ADZUNA_COUNTRY (loads .env first).

        Raises:
            RuntimeError: If the id or key is missing — caller falls back to the mock.
        """
        load_dotenv()
        app_id = os.environ.get("ADZUNA_APP_ID")
        app_key = os.environ.get("ADZUNA_APP_KEY")
        if not (app_id and app_key):
            raise RuntimeError(
                "ADZUNA_APP_ID / ADZUNA_APP_KEY are not set. Add them to your "
                "environment or .env."
            )
        return cls(app_id, app_key, os.environ.get("ADZUNA_COUNTRY", "it"))

    async def search(self, query: str) -> list[Job]:
        """Fetch one page of jobs for the query from Adzuna.

        Args:
            query: The job query to search for.

        Returns:
            The page's jobs (malformed entries skipped).
        """
        url = f"{self._BASE}/{self._country}/search/1"
        fields = _extract(query)
        console.log(f"  [blue]adzuna[/] {fields}")
        params: dict[str, str | int] = {
            "app_id": self._app_id,
            "app_key": self._app_key,
            "results_per_page": self._per_page,
            **fields,
        }
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(url, params=params)
            resp.raise_for_status()
            return _parse(resp.json())


# The "1"-or-absent boolean filters: any truthy LLM value becomes "1", else dropped.
_FLAGS = {"salary_include_unknown", "full_time", "part_time", "contract", "permanent"}

# Every search-shaping param the LLM may set. Whitelist = trust boundary: keys
# outside it (app_id/app_key/country/page, or anything hallucinated) are dropped
# so the model can never tamper with credentials, the endpoint, or paging.
_ALLOWED = {
    "what", "what_and", "what_phrase", "what_or", "what_exclude", "title_only",
    "where", "distance", "max_days_old", "category", "sort_dir", "sort_by",
    "salary_min", "salary_max", "company",
    *(f"location{i}" for i in range(8)),
    *_FLAGS,
}  # fmt: skip

_EXTRACT_SYSTEM = (
    "You convert a natural-language job search into Adzuna search parameters. "
    "Return ONLY a JSON object; include a key ONLY when the query clearly implies "
    "it and omit every other key. Never invent values. Keys you may use:\n"
    '- "what": keywords (role / title / skills), space-separated\n'
    '- "what_and": keywords that must ALL appear\n'
    '- "what_phrase": an exact phrase that must appear\n'
    '- "what_or": keywords where at least one must appear\n'
    '- "what_exclude": keywords to exclude\n'
    '- "title_only": keywords that must be in the job title\n'
    '- "where": location (place name or postcode)\n'
    '- "distance": integer search radius in km from "where"\n'
    '- "category": a job category tag\n'
    '- "company": a specific company name\n'
    '- "max_days_old": integer maximum age of the posting in days\n'
    '- "salary_min" / "salary_max": integer salary bounds\n'
    '- "salary_include_unknown": "1" to include jobs with no listed salary\n'
    '- "full_time" / "part_time" / "contract" / "permanent": "1" to keep only that type\n'
    '- "sort_by": one of "default", "hybrid", "date", "salary", "relevance"\n'
    '- "sort_dir": "up" or "down"\n'
    "No prose, no code fences. "
    'Example: {"what": "java developer", "where": "milano", "full_time": "1"}'
)


def _extract(query: str) -> dict[str, str | int]:
    """Use the LLM to turn a natural-language query into Adzuna search params.

    Adzuna matches `what` against posting text and `where` against location (plus
    a dozen optional filters), so a query like "remote senior java jobs in milano
    over 50k" only works once it is split into the right fields. On any failure
    (LLM down, junk reply, bad JSON) it falls back to the whole query as `what` —
    today's behaviour — so search never breaks.

    Args:
        query: The natural-language job query.

    Returns:
        A dict of Adzuna params (always at least ``what``), whitelisted and
        type-normalized by :func:`_normalize`.
    """
    try:
        # ponytail: sync LLM call inside async search, same as refine()'s — fine
        # at this scale; make it async if it ever shows up in latency.
        client, model = openrouter_client()
        reply = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": query},
            ],
        )
        return _normalize(_json_object(reply.choices[0].message.content or ""), query)
    except Exception:
        # ponytail: any LLM/JSON failure -> whole query as `what` (safe floor).
        return {"what": query}


def _normalize(data: dict[str, Any], query: str) -> dict[str, str | int]:
    """Whitelist and type-coerce a raw LLM field dict into Adzuna params.

    Drops keys outside :data:`_ALLOWED` (the trust boundary), coerces the boolean
    filters to "1"-or-absent, keeps numeric fields as ints, strips blank strings,
    and guarantees a non-empty ``what`` (falling back to the whole query).

    Args:
        data: The JSON object the LLM returned.
        query: The original query, used as the ``what`` fallback.

    Returns:
        Clean params ready to merge into the Adzuna request.
    """
    fields: dict[str, str | int] = {}
    for key, value in data.items():
        if key not in _ALLOWED or value is None:
            continue
        if key in _FLAGS:
            if value in (True, 1, "1", "true", "True"):
                fields[key] = "1"
            continue
        if isinstance(value, bool):  # a non-flag boolean is junk
            continue
        if isinstance(value, (int, float)):
            fields[key] = int(value)
            continue
        text = str(value).strip()
        if text:
            fields[key] = text
    fields["what"] = str(fields.get("what", "")).strip() or query
    return fields


def _json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object out of an LLM reply, tolerating fences/preamble.

    Slices from the first ``{`` to the last ``}`` so a reply wrapped in ```json
    fences or with leading prose still parses.

    Args:
        text: The model's raw reply.
    """
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def _salary(result: dict[str, Any]) -> str:
    """Format an Adzuna entry's salary range as a RAL string, or "" if it has none.

    Args:
        result: One Adzuna /search result (may carry salary_min / salary_max).

    Returns:
        "€min–€max", or "€amount" when min == max, or "" when neither is present.
    """
    nums = [
        int(n)
        for n in (result.get("salary_min"), result.get("salary_max"))
        if isinstance(n, (int, float))
    ]
    if not nums:
        return ""
    lo, hi = min(nums), max(nums)
    # ponytail: € assumes the default 'it'/EUR scope; map per-country if it widens.
    return f"€{lo:,}" if lo == hi else f"€{lo:,}–€{hi:,}"


def _parse(payload: dict[str, Any]) -> list[Job]:
    """Map an Adzuna search response into Jobs, skipping entries missing id or title.

    Args:
        payload: The decoded Adzuna /search JSON.
    """
    jobs: list[Job] = []
    results: list[dict[str, Any]] = payload.get("results", [])
    for result in results:
        job_id, title = result.get("id"), result.get("title")
        if not (job_id and title):
            continue  # need an id to dedupe and a title to show
        # `or {}` tolerates Adzuna returning null for a nested object.
        company: dict[str, Any] = result.get("company") or {}
        location: dict[str, Any] = result.get("location") or {}
        jobs.append(
            Job(
                id=str(job_id),
                title=str(title),
                company=str(company.get("display_name", "")),
                location=str(location.get("display_name", "")),
                description=str(result.get("description", "")),
                url=str(result.get("redirect_url", "")),
                salary=_salary(result),
            )
        )
    return jobs


if __name__ == "__main__":
    # ponytail: check the JSON->Job parser (skips malformed) and mock determinism,
    # both network-free. The HTTP call itself is left to a live run.
    import asyncio

    sample: dict[str, Any] = {
        "results": [
            {
                "id": 123,
                "title": "Java Developer",
                "description": "Spring, JPA",
                "redirect_url": "https://adzuna.example/123",
                "company": {"display_name": "Acme"},
                "location": {"display_name": "Milano"},
                "salary_min": 30000,
                "salary_max": 45000.0,
            },
            {"id": None, "title": "No id"},  # skipped
            {"title": "Missing id"},  # skipped
            {"id": 456},  # skipped: missing title
            {"id": 789, "title": "Python Engineer", "company": None},  # null nested
        ]
    }
    parsed = _parse(sample)
    assert [j.id for j in parsed] == ["123", "789"], parsed
    java = parsed[0]
    assert java.company == "Acme" and java.location == "Milano", java
    assert java.description == "Spring, JPA" and java.url.endswith("/123"), java
    assert java.salary == "€30,000–€45,000", java  # range, ints + floats
    assert parsed[1].company == "" and parsed[1].location == "", parsed[1]  # null -> ""
    assert parsed[1].salary == "", parsed[1]  # no salary fields -> ""

    # _salary: range, single value (min == max), and absent.
    assert _salary({"salary_min": 30000, "salary_max": 30000}) == "€30,000"
    assert _salary({"salary_max": 50000}) == "€50,000"  # one bound is enough
    assert _salary({}) == ""

    mock = asyncio.run(MockProvider().search("python dev"))
    assert len(mock) == 5 and all(isinstance(j, Job) for j in mock)

    # _json_object tolerates the ways a free model wraps its reply.
    assert _json_object('{"what": "java", "where": "forli"}') == {
        "what": "java",
        "where": "forli",
    }
    assert _json_object('```json\n{"what": "java", "where": ""}\n```')["what"] == "java"
    assert _json_object('here you go: {"what": "x"} ok')["what"] == "x"

    # _normalize whitelists (drops scaffolding/junk), coerces flags + numbers,
    # and guarantees a usable `what`.
    norm = _normalize(
        {
            "what": "java",
            "where": "forli",
            "full_time": True,  # truthy flag -> "1"
            "permanent": "0",  # falsy flag -> dropped
            "salary_min": 30000,  # int kept
            "distance": "10",  # numeric string kept
            "where_typo": "x",  # not allowed -> dropped
            "app_id": "leak",  # scaffolding -> dropped
        },
        "orig",
    )
    assert norm == {
        "what": "java",
        "where": "forli",
        "full_time": "1",
        "salary_min": 30000,
        "distance": "10",
    }, norm
    assert _normalize({}, "fallback query") == {
        "what": "fallback query"
    }  # empty -> what
    assert _normalize({"what": "  "}, "fb") == {"what": "fb"}  # blank what -> fallback
    print("providers self-check ok")
