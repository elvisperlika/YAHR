"""The Orchestrator's network: where it discovers agents over A2A.

The Orchestrator learns each agent's identity, description, and skills at runtime
by fetching its Agent Card from the well-known URI (/.well-known/agent-card.json)
— the A2A agent-discovery mechanism. This file only lists *where* to look;
capabilities are not duplicated here, they come from the live cards.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentAddress:
    """Where an agent is reachable over A2A.

    Attributes:
        ip: The agent's IP address (or hostname).
        port: The agent's port.
    """

    ip: str
    port: int

    @property
    def url(self) -> str:
        """The agent's base A2A URL (also where its server binds)."""
        return f"http://{self.ip}:{self.port}"


# Canonical agent names: the Agent Cards advertise these, and the Orchestrator
# matches on them to chain the searcher's jobs into the ranker. Single source of
# truth — the cards import these so the names can never drift apart.
JOB_SEARCHER_NAME = "Job Searcher Agent"
RANKER_NAME = "Ranker Agent"

# Single source of truth for each agent's address: both its server (serve) and
# the discovery list below derive from it.
JOB_SEARCHER_ADDRESS = AgentAddress("127.0.0.1", 8002)
RANKER_ADDRESS = AgentAddress("127.0.0.1", 8003)

# Base URLs the Orchestrator probes for agent cards. Only running agents that
# actually serve a card are discovered and become routing candidates; add
# endpoints here as more agents come online.
AGENT_URLS: list[str] = [JOB_SEARCHER_ADDRESS.url, RANKER_ADDRESS.url]
