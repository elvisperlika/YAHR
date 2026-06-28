"""Shared data types for the Job Searcher (no behaviour, no dependencies)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    """A single open position.

    Attributes:
        id: Stable identifier used to dedupe across query refinements.
        title: Job title.
        company: Hiring company's display name ("" if Adzuna omits it).
        location: Human-readable location ("" if omitted).
        description: Posting body — the main signal the ranker scores against.
        url: Link to the full listing (Adzuna redirect_url), to apply.
    """

    id: str
    title: str
    # ponytail: optional so a partial Adzuna entry still parses (default "").
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    # ponytail: salary_min/max, contract_time/type, category, created also exist
    # in the API — add them here when the ranker or display actually reads them.
