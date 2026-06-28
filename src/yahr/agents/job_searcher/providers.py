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

from yahr.agents.job_searcher.models import Job
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


_EXTRACT_SYSTEM = (
    "You turn a natural-language job search into Adzuna API fields. Reply with "
    'ONLY a JSON object with two keys: "what" (the role, title or skills to '
    'search for) and "where" (the location, or "" if the query names none). No '
    "other keys, no prose, no code fences."
)


def _extract(query: str) -> dict[str, str]:
    """Use the LLM to split a natural-language query into Adzuna {what, where}.

    Adzuna matches `what` against posting text and `where` against location, so a
    query like "java developer in forli" only works once it is split. On any
    failure (LLM down, junk reply, bad JSON) it falls back to the whole query as
    `what` — today's behaviour — so search never breaks.

    Args:
        query: The natural-language job query.

    Returns:
        {"what": ...} plus "where" when a location was found.
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
        data = _json_object(reply.choices[0].message.content or "")
        what = str(data.get("what") or "").strip() or query
        where = str(data.get("where") or "").strip()
    except Exception:
        # ponytail: any LLM/JSON failure -> whole query as `what` (safe floor).
        return {"what": query}
    return {"what": what, "where": where} if where else {"what": what}


def _json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object out of an LLM reply, tolerating fences/preamble.

    Slices from the first ``{`` to the last ``}`` so a reply wrapped in ```json
    fences or with leading prose still parses.

    Args:
        text: The model's raw reply.
    """
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


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
    assert parsed[1].company == "" and parsed[1].location == "", parsed[1]  # null -> ""

    mock = asyncio.run(MockProvider().search("python dev"))
    assert len(mock) == 5 and all(isinstance(j, Job) for j in mock)

    # _json_object tolerates the ways a free model wraps its reply.
    assert _json_object('{"what": "java", "where": "forli"}') == {
        "what": "java",
        "where": "forli",
    }
    assert _json_object('```json\n{"what": "java", "where": ""}\n```')["what"] == "java"
    assert _json_object('here you go: {"what": "x"} ok')["what"] == "x"
    print("providers self-check ok")
