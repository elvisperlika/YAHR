"""LLM-routing Orchestrator built on A2A agent discovery.

It discovers agents at runtime by fetching their Agent Cards from the well-known
URI (/.well-known/agent-card.json) of each configured endpoint, asks an LLM which
discovered agent best fits the query, then forwards the message to it over A2A.
Only agents that are actually running (and thus serving a card) are routable.
"""

from collections.abc import AsyncIterator

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers import get_message_text, new_text_message
from a2a.types import AgentCard, Role, SendMessageRequest, TaskState

from yahr.agents.roster import AGENT_URLS
from yahr.config import openrouter_client

# A status update relayed to the CLI: (state, text), e.g. ("working", "Querying…").
Update = tuple[str, str]

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


def _state_label(state: TaskState) -> str:
    """Human-readable lowercase name for a protobuf TaskState (e.g. 'working')."""
    return TaskState.Name(state).removeprefix("TASK_STATE_").lower()


async def route(query: str) -> AsyncIterator[Update]:
    """Discover, route to the LLM-chosen agent, and stream the task's status.

    Yields (state, text) pairs as the chosen agent works — ending with a
    ("completed", result) pair, or ("error", reason) if routing fails.

    Args:
        query: The user's natural-language request.
    """
    # ponytail: short connect timeout fails fast on dead endpoints; long read
    # timeout keeps the task's status stream open while the agent works.
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=3.0)) as http:
        cards = await discover(http)
        if not cards:
            yield "error", "No agents reachable."
            return
        name = choose_agent(query, cards)
        if name is None:
            yield "error", "No discovered agent fits that request."
            return
        _url, card = cards[name]
        yield "routing", f"Routed to {name}"
        async for update in _send(http, card, query):
            yield update


async def _send(
    http: httpx.AsyncClient, card: AgentCard, query: str
) -> AsyncIterator[Update]:
    """Stream a discovered agent's task status as (state, text) pairs.

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
            text = (
                get_message_text(status.message) if status.HasField("message") else ""
            )
            yield _state_label(status.state), text
        elif resp.HasField("message"):
            yield "completed", get_message_text(resp.message)
        elif resp.HasField("task"):
            yield _state_label(resp.task.status.state), ""


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
    print("orchestrator self-check ok")
