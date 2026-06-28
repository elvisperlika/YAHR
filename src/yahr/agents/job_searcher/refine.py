"""Query refinement for the goal-seeking Job Searcher.

When a search round returns too few jobs, the agent broadens the query and tries
again. Refinement is LLM-first (it knows synonyms and adjacent roles) with a
deterministic heuristic fallback, so the loop keeps making progress even when the
LLM is unreachable, rate-limited, or returns junk. The heuristic always reduces
specificity (or, at one token, returns the query unchanged so the search loop
converges) — it never stalls.
"""

from rich.console import Console

from yahr.config import openrouter_client

# ponytail: same server-side log as the executor — shows the refine decisions in
# the agent's own process (LLM hit, fallback reason, broadened query).
console = Console()

# Qualifier words that narrow a job query; dropped first when broadening.
_QUALIFIERS = {"senior", "junior", "mid", "lead", "remote", "hybrid", "contract"}

_REFINE_SYSTEM = (
    "You refine job-search queries for a job board. The current query returned "
    "too few relevant results. Produce ONE broader or adjacent query likely to "
    "surface more postings for the same kind of role (use synonyms or related "
    "titles, widen scope). Reply with ONLY the query string — no quotes, no "
    "explanation, no preamble."
)


def refine(query: str, found: int, target: int) -> str:
    """Produce a broader query for the next search round.

    Tries the LLM first; on any failure (unreachable, rate-limited, junk reply)
    falls back to the deterministic heuristic, which always returns something.

    Args:
        query: The current query that returned too few results.
        found: How many jobs the current query has accumulated so far.
        target: How many jobs the goal wants.

    Returns:
        A new query to try next. May equal ``query`` only when it is a single
        token and cannot be broadened further (the search loop reads that as
        convergence and stops).
    """
    console.log(f"  [magenta]refine[/] {query!r} — {found}/{target} jobs, broadening")
    try:
        candidate = _llm_refine(query, found, target)
        if candidate is None:
            console.log("    [yellow]llm reply unusable[/] → heuristic")
    except Exception as exc:
        # ponytail: broad except on purpose — a free/paid LLM has many failure
        # modes, and the heuristic is a safe floor that always broadens.
        console.log(f"    [yellow]llm error[/] {type(exc).__name__} → heuristic")
        candidate = None
    new_query = candidate or _broaden(query)
    console.log(
        f"    [magenta]{'llm' if candidate else 'heuristic'} →[/] {new_query!r}"
    )
    return new_query


def _llm_refine(query: str, found: int, target: int) -> str | None:
    """Ask the LLM for a broader query, or return None if its reply is unusable.

    Args:
        query: The current query that returned too few results.
        found: How many jobs the current query has accumulated so far.
        target: How many jobs the goal wants.

    Returns:
        A cleaned candidate query, or None if the model returned nothing usable.
    """
    client, model = openrouter_client()
    reply = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _REFINE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Current query: {query!r}\n"
                    f"It returned {found} jobs; the goal wants {target}. "
                    "Give a broader or adjacent query."
                ),
            },
        ],
    )
    return _clean(reply.choices[0].message.content, query)


def _clean(raw: str | None, query: str) -> str | None:
    """Sanitize an LLM reply into a usable query, or None.

    Rejects empty replies, over-long ones (the model leaked prose instead of a
    query), and replies identical to the current query (no progress).

    Args:
        raw: The model's raw reply content.
        query: The current query, to reject a no-op refinement.

    Returns:
        The cleaned first line, or None if it is unusable.
    """
    text = (raw or "").strip().strip("\"'`")
    if not text:
        return None
    # ponytail: take the first line and length-cap it; a strict prompt usually
    # yields a bare query, this just guards the occasional leaked preamble.
    candidate = text.splitlines()[0].strip()
    if not candidate or len(candidate) > 120 or candidate.lower() == query.lower():
        return None
    return candidate


def _broaden(query: str) -> str:
    """Deterministically broaden a query by shedding one term.

    Drops the first qualifier word (senior, remote, …) if present, otherwise the
    trailing token. A single-token query is returned unchanged — there is nothing
    left to broaden, and the search loop treats "no new jobs" as convergence.

    Args:
        query: The query to broaden.

    Returns:
        A less specific query, or ``query`` itself when it is a single token.
    """
    tokens = query.split()
    if len(tokens) <= 1:
        return query
    for i, token in enumerate(tokens):
        if token.lower() in _QUALIFIERS:
            del tokens[i]
            break
    else:
        tokens.pop()
    return " ".join(tokens)


if __name__ == "__main__":
    # ponytail: network-free checks of the parts refine() falls back to and the
    # validation that decides when to fall back.
    assert _broaden("senior java developer milano") == "java developer milano"
    assert _broaden("java developer milano") == "java developer"  # no qualifier
    assert _broaden("java") == "java"  # one token -> unchanged, loop converges

    assert _clean("  'python engineer'  ", "java dev") == "python engineer"
    assert _clean("java dev", "java dev") is None  # identical -> no progress
    assert _clean("", "x") is None
    assert _clean(None, "x") is None
    assert _clean("x" * 200, "q") is None  # leaked prose -> rejected
    print("refine self-check ok")
