"""Resolve a configured :class:`JobProvider` and run searches.

The CLI calls :func:`get_provider` (which honors the ``JOBS_PROVIDER`` env var)
and :func:`search_jobs_sync`, a thin synchronous wrapper around the provider's
async ``search`` so Typer commands stay sync.
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from agents.job_searcher.adzuna import AdzunaProvider
from agents.job_searcher.provider import JobPosting, JobProvider

DEFAULT_PROVIDER = "adzuna"

#: Registry of provider name → implementation.
_PROVIDERS: dict[str, type[JobProvider]] = {
    "adzuna": AdzunaProvider,
}


class UnknownProviderError(RuntimeError):
    """Raised when the configured provider name has no implementation."""


def get_provider(name: str | None = None) -> JobProvider:
    """Instantiate the job provider named ``name``.

    When ``name`` is ``None`` the ``JOBS_PROVIDER`` env var is consulted,
    falling back to :data:`DEFAULT_PROVIDER`. A real env var takes precedence
    over the ``.env`` file.
    """
    if name is None:
        load_dotenv(override=False)
        name = os.getenv("JOBS_PROVIDER", "").strip() or DEFAULT_PROVIDER

    name = name.strip().lower()
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError:
        raise UnknownProviderError(
            f"unknown job provider '{name}'. Supported: "
            f"{', '.join(sorted(_PROVIDERS))}."
        )
    return provider_cls()


def search_jobs_sync(
    *,
    what: str,
    where: str = "",
    limit: int = 20,
    with_salary: bool = False,
    provider: JobProvider | None = None,
) -> list[JobPosting]:
    """Synchronous wrapper around :meth:`JobProvider.search`.

    Uses ``provider`` when given, otherwise resolves one via :func:`get_provider`.
    """
    provider = provider or get_provider()
    return asyncio.run(
        provider.search(what=what, where=where, limit=limit, with_salary=with_salary)
    )
