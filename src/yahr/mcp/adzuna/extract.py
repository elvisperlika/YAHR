"""Natural language → Adzuna search parameters (the LLM-mapping context).

Turns a free-text job query into the dict of Adzuna `/search` params via the
LLM, behind a whitelist trust boundary so the model can never set credentials,
the endpoint, or paging. On any failure it falls back to the whole query as
`what`, so search never breaks.
"""

import json
from typing import Any

from yahr.config import openrouter_client

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
    '- "salary_min" / "salary_max": integer salary bounds. To return ONLY jobs '
    'that list a salary (user wants "with salary" / "salary shown"), set '
    '"salary_min": 1 (or the real minimum) and do NOT set salary_include_unknown\n'
    '- "salary_include_unknown": "1" to ALSO keep jobs with no listed salary '
    "when a salary bound is set; omit it to drop unlisted-salary jobs\n"
    '- "full_time" / "part_time" / "contract" / "permanent": "1" to keep only that type\n'
    '- "sort_by": one of "default", "hybrid", "date", "salary", "relevance"\n'
    '- "sort_dir": "up" or "down"\n'
    "No prose, no code fences. "
    'Example: {"what": "java developer", "where": "milano", "full_time": "1"}'
)


def to_params(query: str) -> dict[str, str | int]:
    """Use the LLM to turn a natural-language query into Adzuna search params.

    Adzuna matches `what` against posting text and `where` against location (plus
    a dozen optional filters), so a query like "remote senior java jobs in milano
    over 50k" only works once it is split into the right fields. On any failure
    (LLM down, junk reply, bad JSON) it falls back to the whole query as `what`.

    Args:
        query: The natural-language job query.

    Returns:
        A dict of Adzuna params (always at least ``what``), whitelisted and
        type-normalized by :func:`_normalize`.
    """
    try:
        # ponytail: sync LLM call inside the async search path — fine at this
        # scale; make it async if it ever shows up in latency.
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


if __name__ == "__main__":
    # ponytail: the network-free pieces — how a free model's reply is unwrapped
    # and whitelisted. to_params itself calls the LLM, left to a live run.

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
    print("adzuna extract self-check ok")
