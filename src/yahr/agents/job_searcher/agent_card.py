"""The Job Searcher's public A2A agent card (served at the well-known path)."""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.utils.constants import TransportProtocol


def agent_card(url: str) -> AgentCard:
    """Build the Job Searcher's public agent card served at the well-known path.

    Args:
        url: Base URL the agent is reachable at (its JSONRPC interface).
    """
    return AgentCard(
        name="Job Searcher Agent",
        description="Discovers open positions via some APIs.",
        version="0.1.0",
        supported_interfaces=[
            AgentInterface(protocol_binding=TransportProtocol.JSONRPC, url=url)
        ],
        # streaming=True so the orchestrator receives task status updates live.
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="search-jobs",
                name="Search jobs",
                description="Find open positions matching a natural-language query.",
                tags=["jobs", "search"],
            )
        ],
    )
