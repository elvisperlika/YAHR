"""Adzuna HTTP access and response parsing (the job-board client context).

Reads credentials from the environment, fetches one /search page for a query
(delegating the natural-language → params step to extract.py), and maps the
response into Jobs, skipping malformed entries. This module only speaks to
Adzuna over HTTPS; it knows nothing about MCP.
"""

import os
from typing import Any

import httpx
from rich.console import Console

from yahr.agents.models.job import Job
from yahr.config import load_dotenv
from yahr.mcp.adzuna.extract import to_params

# ponytail: server-side log shows the structured query Adzuna actually receives
# (never the app_id/key).
console = Console()

_BASE = "https://api.adzuna.com/v1/api/jobs"


def _credentials() -> tuple[str, str, str]:
    """Read Adzuna credentials and country from the environment (loads .env first).

    Returns:
        An (app_id, app_key, country) tuple.

    Raises:
        RuntimeError: If the id or key is missing.
    """
    load_dotenv()
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY are not set. Add them to your "
            "environment or .env."
        )
    return app_id, app_key, os.environ.get("ADZUNA_COUNTRY", "it")


async def search_adzuna(query: str) -> list[Job]:
    """Fetch one page of jobs for the query from Adzuna.

    Args:
        query: The natural-language job query.

    Returns:
        The page's jobs (malformed entries skipped).
    """
    app_id, app_key, country = _credentials()
    fields = to_params(query)
    console.log(f"  [blue]adzuna[/] {fields}")
    params: dict[str, str | int] = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": 20,
        **fields,
    }
    url = f"{_BASE}/{country}/search/1"
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(url, params=params)
        resp.raise_for_status()
        return _parse(resp.json())


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
    # ponytail: the network-free pieces — the JSON->Job parser (skips malformed)
    # and the salary formatter. The HTTP call is left to a live run.
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
    print("adzuna client self-check ok")
