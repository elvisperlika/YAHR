"""Turn resume markdown into a structured :class:`~models.resume.Resume`.

This module is transport-agnostic: it knows nothing about A2A. It takes
markdown in and returns a ``Resume`` out, calling an OpenRouter-hosted LLM to do
the extraction. The A2A layer (``executor`` / ``server``) wraps this.
"""

from __future__ import annotations

import asyncio
import json

from openai import AsyncOpenAI, BadRequestError

from agents.resume_builder.config import OpenRouterConfig, load_config
from models import (
    Education,
    PersonalInfo,
    Project,
    Resume,
    Skills,
    WorkExperience,
)

# The shape we ask the model to return. Keep this in sync with models/resume.py.
_JSON_SHAPE = """{
  "personal_info": {
    "name": "string",
    "email": "string",
    "phone": "string",
    "github": "string",
    "linkedin": "string"
  },
  "education": [
    {"degree": "string", "institution": "string", "location": "string",
     "date": "string", "description": "string"}
  ],
  "work_experience": [
    {"title": "string", "company": "string", "location": "string",
     "period": "string", "description": "string", "skills": ["string"]}
  ],
  "projects": [
    {"name": "string", "description": "string",
     "technologies": ["string"], "url": "string"}
  ],
  "skills": {
    "hard": ["string"], "soft": ["string"], "languages": ["string"]
  }
}"""

_SYSTEM_PROMPT = (
    "You are an expert resume parser. You convert a resume written in Markdown "
    "into a single structured JSON object. Extract every field you can find. "
    "Use empty strings or empty arrays for anything missing — never invent "
    "facts that are not present in the text. Respond with JSON only, no prose, "
    "no markdown code fences."
)

_USER_PROMPT_TEMPLATE = (
    "Parse the following resume into a JSON object matching EXACTLY this shape "
    "(same keys, same nesting):\n\n{shape}\n\n"
    "Notes:\n"
    "- 'period' / 'date' should keep the original wording (e.g. 'May 2024 - Jul 2024').\n"
    "- 'skills' under a work experience are the technologies used in that role.\n"
    "- Put general technical skills under skills.hard, interpersonal ones under "
    "skills.soft, and spoken/written languages under skills.languages.\n\n"
    "Resume markdown:\n---\n{markdown}\n---"
)


class ResumeParseError(RuntimeError):
    """Raised when the model output cannot be turned into a ``Resume``."""


def _extract_json_object(text: str) -> dict:
    """Best-effort extraction of a JSON object from a model response.

    Handles clean JSON, ```json fenced blocks, and stray prose around the
    object by falling back to the outermost ``{...}`` span.
    """
    text = text.strip()
    if not text:
        raise ResumeParseError("Model returned an empty response.")

    # Strip a leading/trailing markdown code fence if present.
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip("` \n")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ResumeParseError(
                f"Could not parse JSON from model response: {exc}"
            ) from exc
    raise ResumeParseError("No JSON object found in model response.")


def _as_str(value: object) -> str:
    """Safely convert a value to a stripped string, or return an empty string."""
    return value.strip() if isinstance(value, str) else ""


def _as_str_list(value: object) -> list[str]:
    """Safely convert a value to a list of stripped strings, or return an empty list."""
    if isinstance(value, list):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return []


def resume_from_dict(data: dict, raw_text: str = "") -> Resume:
    """Defensively map a parsed JSON dict onto the ``Resume`` dataclasses.

    Unknown keys are ignored and missing keys fall back to sensible empties, so
    a slightly-off model response still yields a usable ``Resume``.
    """
    if not isinstance(data, dict):
        raise ResumeParseError("Expected a JSON object at the top level.")

    pi = data.get("personal_info") or {}
    if not isinstance(pi, dict):
        pi = {}
    personal_info = PersonalInfo(
        name=_as_str(pi.get("name")),
        email=_as_str(pi.get("email")),
        phone=_as_str(pi.get("phone")),
        github=_as_str(pi.get("github")),
        linkedin=_as_str(pi.get("linkedin")),
    )

    education = [
        Education(
            degree=_as_str(e.get("degree")),
            institution=_as_str(e.get("institution")),
            location=_as_str(e.get("location")),
            date=_as_str(e.get("date")),
            description=_as_str(e.get("description")),
        )
        for e in (data.get("education") or [])
        if isinstance(e, dict)
    ]

    work_experience = [
        WorkExperience(
            title=_as_str(w.get("title")),
            company=_as_str(w.get("company")),
            location=_as_str(w.get("location")),
            period=_as_str(w.get("period")),
            description=_as_str(w.get("description")),
            skills=_as_str_list(w.get("skills")),
        )
        for w in (data.get("work_experience") or [])
        if isinstance(w, dict)
    ]

    projects = [
        Project(
            name=_as_str(p.get("name")),
            description=_as_str(p.get("description")),
            technologies=_as_str_list(p.get("technologies")),
            url=_as_str(p.get("url")),
        )
        for p in (data.get("projects") or [])
        if isinstance(p, dict)
    ]

    sk = data.get("skills") or {}
    if not isinstance(sk, dict):
        sk = {}
    skills = Skills(
        hard=_as_str_list(sk.get("hard")),
        soft=_as_str_list(sk.get("soft")),
        languages=_as_str_list(sk.get("languages")),
    )

    return Resume(
        personal_info=personal_info,
        education=education,
        work_experience=work_experience,
        projects=projects,
        skills=skills,
        raw_text=raw_text,
    )


async def _complete(
    client: AsyncOpenAI, config: OpenRouterConfig, markdown: str
) -> str:
    """Call the model, asking for JSON; degrade gracefully if the free model
    does not support the ``json_object`` response format."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _USER_PROMPT_TEMPLATE.format(
                shape=_JSON_SHAPE, markdown=markdown
            ),
        },
    ]
    kwargs = {
        "model": config.model,
        "messages": messages,
        "temperature": 0,
        "extra_headers": config.extra_headers or None,
    }
    try:
        resp = await client.chat.completions.create(
            response_format={"type": "json_object"}, **kwargs
        )
    except BadRequestError:
        # Many free models reject the json_object response_format; retry without
        # it. Other errors (auth, network, rate limits) propagate unchanged.
        resp = await client.chat.completions.create(**kwargs)

    if not resp.choices:
        raise ResumeParseError("Model returned no choices.")
    return resp.choices[0].message.content or ""


async def build_resume_from_markdown(
    markdown: str,
    config: OpenRouterConfig | None = None,
    client: AsyncOpenAI | None = None,
) -> Resume:
    """Parse resume ``markdown`` into a :class:`Resume` via OpenRouter.

    Args:
        markdown: The resume content (e.g. ``output/resume.md``).
        config: OpenRouter settings. Loaded from the environment if omitted.
        client: A pre-built ``AsyncOpenAI`` client (useful for tests). Created
            from ``config`` if omitted.

    Raises:
        MissingAPIKeyError: if no API key is configured (via ``load_config``).
        ResumeParseError: if the model output cannot be parsed.
    """
    if not markdown or not markdown.strip():
        raise ResumeParseError("Resume markdown is empty.")

    config = config or load_config()
    owns_client = client is None
    client = client or AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)
    try:
        content = await _complete(client, config, markdown)
    finally:
        if owns_client:
            await client.close()

    data = _extract_json_object(content)
    return resume_from_dict(data, raw_text=markdown)


def build_resume_from_markdown_sync(
    markdown: str, config: OpenRouterConfig | None = None
) -> Resume:
    """Synchronous wrapper around :func:`build_resume_from_markdown`."""
    return asyncio.run(build_resume_from_markdown(markdown, config=config))
