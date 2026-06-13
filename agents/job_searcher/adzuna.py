"""Adzuna implementation of :class:`~agents.job_searcher.provider.JobProvider`.

Adzuna aggregates listings across many countries (Italy included) behind a
simple JSON API. Credentials are a public ``app_id`` plus a secret ``app_key``;
both go on every request as query params. Get them at developer.adzuna.com.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

from agents.job_searcher.provider import JobPosting, JobProvider

DEFAULT_BASE_URL = "https://api.adzuna.com/v1/api/jobs"
DEFAULT_COUNTRY = "it"


class MissingAdzunaCredentialsError(RuntimeError):
    """Raised when the Adzuna app id / app key are not configured."""


@dataclass(frozen=True)
class AdzunaConfig:
    """Resolved Adzuna connection settings."""

    app_id: str
    app_key: str
    country: str = DEFAULT_COUNTRY
    base_url: str = DEFAULT_BASE_URL

    @classmethod
    def from_env(cls) -> "AdzunaConfig":
        """Build a config from ``ADZUNA_*`` environment variables.

        Reads ``ADZUNA_APP_ID`` and ``ADZUNA_APP_KEY`` (both required) plus the
        optional ``ADZUNA_COUNTRY`` (defaults to ``it``). A real env var takes
        precedence over the ``.env`` file.
        """
        load_dotenv(override=False)

        app_id = os.getenv("ADZUNA_APP_ID", "").strip()
        app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
        if not app_id or not app_key:
            raise MissingAdzunaCredentialsError(
                "ADZUNA_APP_ID and ADZUNA_APP_KEY must be set. Get them at "
                "https://developer.adzuna.com and run `yahr setup-jobs-provider`."
            )

        country = os.getenv("ADZUNA_COUNTRY", "").strip() or DEFAULT_COUNTRY
        return cls(app_id=app_id, app_key=app_key, country=country)


class AdzunaProvider(JobProvider):
    """Search jobs via the Adzuna API."""

    name = "adzuna"

    def __init__(self, config: AdzunaConfig | None = None) -> None:
        self._config = config or AdzunaConfig.from_env()
        self.base_url = self._config.base_url
        # The interface exposes a single ``api_key``; Adzuna also needs app_id.
        self.api_key = self._config.app_key
        self.app_id = self._config.app_id

    async def search(
        self,
        *,
        what: str,
        where: str = "",
        limit: int = 20,
        with_salary: bool = False,
    ) -> list[JobPosting]:
        params = {
            "app_id": self.app_id,
            "app_key": self.api_key,
            "what": what,
            "results_per_page": limit,
            "content-type": "application/json",
        }
        if where:
            params["where"] = where
        if with_salary:
            # Adzuna drops salary-less listings once a salary_min is set, so a
            # floor of 1 keeps only postings that disclose a figure.
            params["salary_min"] = 1

        url = f"{self.base_url}/{self._config.country}/search/1"
        # To receive JSON we must setup the Accept header
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        postings = [self._to_posting(r) for r in data.get("results", [])]
        if with_salary:
            # Guard against any listings the API leaves salary-less.
            postings = [p for p in postings if p.salary_min or p.salary_max]
        return postings

    def _to_posting(self, raw: dict) -> JobPosting:
        """Map one Adzuna result into a normalized :class:`JobPosting`."""
        return JobPosting(
            title=raw.get("title", ""),
            company=raw.get("company", {}).get("display_name", ""),
            location=raw.get("location", {}).get("display_name", ""),
            description=raw.get("description", ""),
            url=raw.get("redirect_url", ""),
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
            contract_type=raw.get("contract_type"),
            created=raw.get("created"),
            source=self.name,
        )
