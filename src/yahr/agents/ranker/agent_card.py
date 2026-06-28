"""The Ranker's public A2A agent card (served at the well-known path)."""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.utils.constants import TransportProtocol

from yahr.agents.roster import RANKER_NAME


def agent_card(url: str) -> AgentCard:
    """Build the Ranker's public agent card served at the well-known path.

    Args:
        url: Base URL the agent is reachable at (its JSONRPC interface).
    """
    return AgentCard(
        name=RANKER_NAME,
        description=(
            "Scores found jobs against your resume and ranks the best matches — "
            "answers which jobs fit you and why. Use for matching, ranking, or "
            "'which job suits me', NOT for plain job search."
        ),
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
                id="rank-jobs",
                name="Rank jobs",
                description="Score and rank open positions against a resume to answer which fit best.",
                tags=["jobs", "ranking", "match"],
            )
        ],
    )
