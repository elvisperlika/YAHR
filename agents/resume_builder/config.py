"""Configuration for the Resume Builder agent.

All values are read from the environment so the same code runs locally and in a
container. Sensible defaults are provided for everything except the API key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class OpenRouterConfig:
    """Resolved OpenRouter connection settings."""

    api_key: str
    base_url: str
    model: str
    title: str = ""

    @property
    def extra_headers(self) -> dict[str, str]:
        """Optional headers OpenRouter uses for attribution (e.g. ``X-Title``)."""
        return {"X-Title": self.title} if self.title else {}


class ConfigError(RuntimeError):
    """Base class for missing/invalid configuration."""


class MissingAPIKeyError(ConfigError):
    """Raised when no OpenRouter API key is configured."""


class MissingBaseURLError(ConfigError):
    """Raised when no OpenRouter Base URL is configured."""


class MissingModelError(ConfigError):
    """Raised when no OpenRouter Model is configured."""


def load_config() -> OpenRouterConfig:
    """Build an :class:`OpenRouterConfig` from environment variables.

    All of the following are required (no defaults):

    - ``API_KEY``
    - ``BASE_URL``
    - ``MODEL``

    Raises:
        MissingAPIKeyError: if ``API_KEY`` is not set.
        MissingBaseURLError: if ``BASE_URL`` is not set.
        MissingModelError: if ``MODEL`` is not set.
    """

    # Load .env into the environment; real env vars take precedence (override=False).
    load_dotenv(override=False)

    api_key = os.getenv("API_KEY", "").strip()
    base_url = os.getenv("BASE_URL", "").strip()
    model = os.getenv("MODEL", "").strip()

    if not api_key:
        raise MissingAPIKeyError(
            "API_KEY is not set. Get a key at "
            "https://openrouter.ai/keys and export it before running the agent."
        )
    if not base_url:
        raise MissingBaseURLError(
            "BASE_URL is not set (e.g. https://openrouter.ai/api/v1)."
        )
    if not model:
        raise MissingModelError(
            "MODEL is not set. Set it to the name of the model you want to use, e.g. gpt-4o-mini."
        )

    return OpenRouterConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        title="YAHR Resume Builder",
    )
