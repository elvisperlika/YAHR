"""Provider-agnostic job-search interface.

A :class:`JobProvider` turns a query into a list of normalized
:class:`JobPosting` objects, so the rest of YAHR (e.g. the ranker) never needs
to know which backend produced them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class JobPosting:
    """A single job listing, normalized across providers."""

    title: str
    company: str
    location: str
    description: str
    url: str
    salary_min: float | None = None
    salary_max: float | None = None
    contract_type: str | None = None
    created: str | None = None
    source: str = ""


class JobProvider(ABC):
    """Interface every job-search backend must implement."""

    #: Short, stable identifier for the provider (e.g. ``"adzuna"``).
    name: str
    base_url: str
    api_key: str | None = None

    @abstractmethod
    async def search(
        self,
        *,
        what: str,
        where: str = "",
        limit: int = 20,
    ) -> list[JobPosting]:
        """Return up to ``limit`` postings matching ``what`` in ``where``.

        Args:
            what: Free-text keywords (role, skills, …).
            where: Location filter; empty means no location constraint.
            limit: Maximum number of postings to return.
        """
        raise NotImplementedError