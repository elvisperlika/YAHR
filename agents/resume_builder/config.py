"""Configuration for the Resume Builder agent.

All values are read from the environment so the same code runs locally and in a
container. Sensible defaults are provided for everything except the API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# OpenRouter exposes an OpenAI-compatible endpoint, so we drive it through the
# ``openai`` SDK by pointing ``base_url`` here.
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# A strong free model on OpenRouter (note the ``:free`` suffix). Free models are
# rate-limited; override with OPENROUTER_MODEL for production use.
DEFAULT_MODEL = "deepseek/deepseek-chat-v3-0324:free"


@dataclass(frozen=True)
class OpenRouterConfig:
    """Resolved OpenRouter connection settings."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    # Optional attribution headers OpenRouter shows on its dashboard/leaderboards.
    referer: str = ""
    title: str = ""

    @property
    def extra_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.title:
            headers["X-Title"] = self.title
        return headers


class MissingAPIKeyError(RuntimeError):
    """Raised when no OpenRouter API key is configured."""


def load_config() -> OpenRouterConfig:
    """Build an :class:`OpenRouterConfig` from environment variables.

    Recognised variables:

    - ``OPENROUTER_API_KEY`` (required)
    - ``OPENROUTER_BASE_URL`` (default: OpenRouter's v1 endpoint)
    - ``OPENROUTER_MODEL`` (default: a free model)
    - ``OPENROUTER_REFERER`` / ``OPENROUTER_TITLE`` (optional attribution)

    Raises:
        MissingAPIKeyError: if ``OPENROUTER_API_KEY`` is not set.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKeyError(
            "OPENROUTER_API_KEY is not set. Get a key at "
            "https://openrouter.ai/keys and export it before running the agent."
        )
    return OpenRouterConfig(
        api_key=api_key,
        base_url=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).strip()
        or DEFAULT_BASE_URL,
        model=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL).strip()
        or DEFAULT_MODEL,
        referer=os.environ.get("OPENROUTER_REFERER", "").strip(),
        title=os.environ.get("OPENROUTER_TITLE", "YAHR Resume Builder").strip(),
    )
