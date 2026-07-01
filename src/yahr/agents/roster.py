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
CV_ASSISTANT_NAME = "CV Assistant Agent"

# Single source of truth for each agent's address: both its server (serve) and
# the discovery list below derive from it.
JOB_SEARCHER_ADDRESS = AgentAddress("127.0.0.1", 8002)
RANKER_ADDRESS = AgentAddress("127.0.0.1", 8003)
# 8004 stays reserved for the C4's planned standalone Orchestrator; 8005/8006 are
# the job-provider MCP servers (below), so the CV Assistant lands on 8007.
CV_ASSISTANT_ADDRESS = AgentAddress("127.0.0.1", 8007)

# Job-provider MCP servers. These are MCP servers, not A2A agents — the Job
# Searcher reaches them as an MCP client, so they stay OUT of AGENT_URLS (the
# Orchestrator must never discover them as routing candidates).
ADZUNA_MCP_ADDRESS = AgentAddress("127.0.0.1", 8005)
MOCK_MCP_ADDRESS = AgentAddress("127.0.0.1", 8006)

# Base URLs the Orchestrator probes for agent cards. Only running agents that
# actually serve a card are discovered and become routing candidates; add
# endpoints here as more agents come online.
AGENT_URLS: list[str] = [
    JOB_SEARCHER_ADDRESS.url,
    RANKER_ADDRESS.url,
    CV_ASSISTANT_ADDRESS.url,
]


if __name__ == "__main__":
    # ponytail: pure invariants — no import here can drift a name/port apart, and
    # a port collision or a leaked MCP server in AGENT_URLS would break routing.
    assert AgentAddress("127.0.0.1", 8002).url == "http://127.0.0.1:8002"

    addresses = [
        JOB_SEARCHER_ADDRESS,
        RANKER_ADDRESS,
        CV_ASSISTANT_ADDRESS,
        ADZUNA_MCP_ADDRESS,
        MOCK_MCP_ADDRESS,
    ]
    ports = [a.port for a in addresses]
    assert len(ports) == len(set(ports)), f"port collision: {ports}"
    assert 8004 not in ports  # reserved for the planned standalone Orchestrator

    # The Orchestrator discovers exactly the three A2A agents, never the MCP servers.
    assert AGENT_URLS == [
        JOB_SEARCHER_ADDRESS.url,
        RANKER_ADDRESS.url,
        CV_ASSISTANT_ADDRESS.url,
    ]
    assert ADZUNA_MCP_ADDRESS.url not in AGENT_URLS
    assert MOCK_MCP_ADDRESS.url not in AGENT_URLS
    print("roster self-check ok")
