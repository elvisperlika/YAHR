"""LLM-routing Orchestrator built on A2A agent discovery.

It discovers agents at runtime by fetching their Agent Cards from the well-known
URI (/.well-known/agent-card.json) of each configured endpoint, asks an LLM which
discovered agent best fits the query, then forwards the message to it over A2A.
Only agents that are actually running (and thus serving a card) are routable.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers import get_data_parts, get_message_text, new_text_message
from a2a.types import AgentCard, Message, Role, SendMessageRequest, TaskState

from yahr.agents.roster import AGENT_URLS, JOB_SEARCHER_NAME, RANKER_NAME
from yahr.config import openrouter_client

# A status update relayed to the CLI: (state, text, data), e.g.
# ("working", "Querying…", None). data carries structured jobs on a job result,
# None otherwise — so the CLI can render cards instead of plain text.
Update = tuple[str, str, Any]

# A discovered agent: its name -> (base url, fetched card).
Discovered = dict[str, tuple[str, AgentCard]]


async def discover(http: httpx.AsyncClient) -> Discovered:
    """Fetch the Agent Card from each configured endpoint (A2A discovery).

    Args:
        http: Async HTTP client used to fetch the well-known cards.

    Returns:
        A mapping of agent name -> (url, card) for every endpoint that serves a
        card; endpoints that are unreachable or cardless are silently skipped.
    """
    found: Discovered = {}
    # ponytail: sequential probe; swap for asyncio.gather if the list grows.
    for url in AGENT_URLS:
        try:
            card = await A2ACardResolver(http, url).get_agent_card()
        except Exception:
            continue  # not running / no card -> not discoverable
        found[card.name] = (url, card)
    return found


def _routing_prompt(cards: Discovered) -> str:
    """Render the discovered cards into the LLM's routing system prompt.

    Args:
        cards: The agents discovered for this request.
    """
    lines: list[str] = []
    for name, (_url, card) in cards.items():
        skills = ", ".join(s.name for s in card.skills)
        suffix = f" (skills: {skills})" if skills else ""
        lines.append(f"- {name}: {card.description}{suffix}")
    return (
        "You are a router for an agent network. Given a user request, reply with "
        "ONLY the exact name of the single best agent to handle it, or 'none' if "
        "no agent fits. Reply with the name and nothing else.\n\n"
        "Agents:\n" + "\n".join(lines)
    )


def choose_agent(query: str, cards: Discovered) -> str | None:
    """Ask the LLM which discovered agent should handle the query.

    Args:
        query: The user's natural-language request.
        cards: The agents discovered for this request.

    Returns:
        A discovered agent name, or None if the LLM declined or returned junk.
    """
    client, model = openrouter_client()
    reply = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _routing_prompt(cards)},
            {"role": "user", "content": query},
        ],
    )
    return _validate(reply.choices[0].message.content, cards)


def _validate(raw: str | None, cards: Discovered) -> str | None:
    """Map a raw LLM reply to a discovered agent name, or None.

    Args:
        raw: The model's answer (expected to be a bare agent name).
        cards: The agents discovered for this request.
    """
    if not raw:
        return None
    candidate = raw.strip().strip(".\"'`").lower()
    for name in cards:
        if name.lower() == candidate:
            return name
    return None


def needs_resume(query: str) -> bool:
    """Ask the LLM whether answering this query benefits from the user's resume.

    A plain job search (by keyword/location) does not; tailoring, ranking,
    matching, or résumé advice does.

    Args:
        query: The user's natural-language request.
    """
    client, model = openrouter_client()
    reply = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Decide whether answering the user's request needs their "
                    "resume/CV. A plain job search by keyword or location does "
                    "NOT need it; tailoring, ranking, matching a profile to "
                    "jobs, or resume advice DOES. Reply ONLY 'yes' or 'no'."
                ),
            },
            {"role": "user", "content": query},
        ],
    )
    return (reply.choices[0].message.content or "").strip().lower().startswith("y")


def _attach(query: str, resume: str) -> str:
    """Append the resume to the query as a labelled section for the agent."""
    return f"{query}\n\n--- Attached resume (Markdown) ---\n{resume}"


# Where the orchestrator caches its artifacts between `ask` runs, so a ranking
# query can reuse them: the jobs the Job Searcher last found, and the last resume
# the user attached. (resume.md is also where `convert` writes and `ask` reads.)
_JOBS_CACHE = Path("output/jobs.md")
_RESUME_CACHE = Path("output/resume.md")


def _cache_jobs(jobs: str) -> None:
    """Persist the Job Searcher's found jobs for a later ranking query."""
    _JOBS_CACHE.parent.mkdir(exist_ok=True)
    _JOBS_CACHE.write_text(jobs)


def _load_jobs() -> str | None:
    """Return the last cached jobs, or None if nothing has been searched yet."""
    return _JOBS_CACHE.read_text() if _JOBS_CACHE.exists() else None


def _cache_resume(resume: str) -> None:
    """Persist the attached resume so a later query can reuse it unattached."""
    if _load_resume() != resume:  # skip the no-op rewrite of an unchanged resume
        _RESUME_CACHE.parent.mkdir(exist_ok=True)
        _RESUME_CACHE.write_text(resume)


def _load_resume() -> str | None:
    """Return the cached resume, or None if none has been attached yet."""
    return _RESUME_CACHE.read_text() if _RESUME_CACHE.exists() else None


def _rank_message(query: str, resume: str | None, jobs: str) -> str:
    """Bundle the ranker's input: the question, the found jobs, and the resume.

    Args:
        query: The user's original question.
        resume: The resume Markdown, or None if there is none.
        jobs: The Job Searcher's result text (its list of found jobs).
    """
    parts = [f"Question: {query}", "", "--- Jobs found ---", jobs or "(none)"]
    if resume:
        parts += ["", "--- Resume (Markdown) ---", resume]
    return "\n".join(parts)


def _state_label(state: TaskState) -> str:
    """Human-readable lowercase name for a protobuf TaskState (e.g. 'working')."""
    return TaskState.Name(state).removeprefix("TASK_STATE_").lower()


async def route(query: str, resume: str | None = None) -> AsyncIterator[Update]:
    """Discover, route to the LLM-chosen agent, and stream the task's status.

    Yields (state, text, data) triples as the chosen agent works — ending with a
    ("completed", result, jobs|None) triple, or ("error", reason, None) if routing
    fails.

    Args:
        query: The user's natural-language request.
        resume: The user's resume Markdown, or None. When present it is cached;
            when absent the last cached resume is used. For a ranking query it is
            sent to the ranker; otherwise the LLM decides per-query whether to
            attach it.
    """
    # Remember the attached resume, and reuse the last one when none is given —
    # mirroring the jobs cache, so a ranking query has the resume even unattached.
    if resume:
        _cache_resume(resume)
    else:
        resume = _load_resume()
    # ponytail: short connect timeout fails fast on dead endpoints; no read
    # timeout because the SSE status stream goes quiet for a whole LLM call —
    # a fixed read deadline just kills legitimate work. Hung agent → Ctrl-C.
    async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=3.0)) as http:
        cards = await discover(http)
        if not cards:
            yield "error", "No agents reachable.", None
            return
        name = choose_agent(query, cards)
        if name is None:
            yield "error", "No discovered agent fits that request.", None
            return
        _url, card = cards[name]

        # The ranker scores jobs against the resume, so it needs the jobs as an
        # artifact. Reuse the jobs the Job Searcher cached on an earlier run;
        # only search afresh (and cache that) if nothing has been searched yet.
        if name == RANKER_NAME:
            jobs = _load_jobs()
            if jobs is None and JOB_SEARCHER_NAME in cards:
                yield "searching", "No cached jobs — searching first", None
                jobs = await _collect(http, cards[JOB_SEARCHER_NAME][1], query)
                if jobs:
                    _cache_jobs(jobs)
            yield "routing", f"Routed to {name}", None
            message = _rank_message(query, resume, jobs or "")
            async for update in _send(http, card, message):
                yield update
            return

        message = query
        if resume and needs_resume(query):
            message = _attach(query, resume)
            yield "context", "Attached your resume", None
        yield "routing", f"Routed to {name}", None
        # Cache whatever the Job Searcher finds, so a later ranking query can
        # rank against it without re-searching.
        async for state, text, data in _send(http, card, message):
            if name == JOB_SEARCHER_NAME and state == "completed":
                _cache_jobs(text)
            yield state, text, data


async def _collect(http: httpx.AsyncClient, card: AgentCard, query: str) -> str:
    """Run an agent to completion and return its final result text.

    Args:
        http: Async HTTP client (reused from discovery).
        card: The agent to drive (here, the Job Searcher).
        query: The text to forward.
    """
    final = ""
    async for state, text, _data in _send(http, card, query):
        if state == "completed":
            final = text
    return final


def _jobs_from(message: Message) -> list[Any] | None:
    """Pull the structured jobs out of a message's data parts, or None.

    Args:
        message: The agent message to inspect (its data parts, if any). Data
            parts are untyped JSON from the SDK, so the dict shape is asserted.
    """
    for part in get_data_parts(message.parts):
        if not isinstance(part, dict):
            continue
        jobs = cast("dict[str, Any]", part).get("jobs")
        if isinstance(jobs, list):
            return cast("list[Any]", jobs)
    return None


async def _send(
    http: httpx.AsyncClient,
    card: AgentCard,
    query: str,
) -> AsyncIterator[Update]:
    """Stream a discovered agent's task status as (state, text, data) triples.

    Args:
        http: Async HTTP client (reused from discovery).
        card: The target agent's discovered Agent Card.
        query: The text to forward.
    """
    client = ClientFactory(ClientConfig(httpx_client=http)).create(card)
    request = SendMessageRequest(message=new_text_message(query, role=Role.ROLE_USER))
    async for resp in client.send_message(request):
        if resp.HasField("status_update"):
            status = resp.status_update.status
            msg = status.message if status.HasField("message") else None
            text = get_message_text(msg) if msg else ""
            yield _state_label(status.state), text, _jobs_from(msg) if msg else None
        elif resp.HasField("message"):
            yield "completed", get_message_text(resp.message), _jobs_from(resp.message)
        elif resp.HasField("task"):
            yield _state_label(resp.task.status.state), "", None


if __name__ == "__main__":
    # ponytail: no-network check of name matching against discovered cards.
    fake: Discovered = {
        "Job Searcher Agent": ("", AgentCard()),
        "Ranker Agent": ("", AgentCard()),
    }
    assert _validate("Job Searcher Agent", fake) == "Job Searcher Agent"
    assert _validate(" job searcher agent. ", fake) == "Job Searcher Agent"
    assert _validate("none", fake) is None
    assert _validate("banana", fake) is None
    assert _validate(None, fake) is None
    attached = _attach("find java jobs", "# CV\nElvis")
    assert attached.startswith("find java jobs\n\n")
    assert "# CV\nElvis" in attached
    # Ranker bundle carries the question, the jobs, and (when present) the resume.
    bundle = _rank_message("best fit?", "# CV\nElvis", "- Job A\n- Job B")
    assert "Question: best fit?" in bundle
    assert "- Job A" in bundle and "# CV\nElvis" in bundle
    assert "Resume" not in _rank_message("best fit?", None, "- Job A")
    print("orchestrator self-check ok")
