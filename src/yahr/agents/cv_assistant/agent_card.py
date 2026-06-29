"""The CV Assistant's public A2A agent card (served at the well-known path)."""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.utils.constants import TransportProtocol

from yahr.agents.roster import CV_ASSISTANT_NAME


def agent_card(url: str) -> AgentCard:
    """Build the CV Assistant's public agent card served at the well-known path.

    Args:
        url: Base URL the agent is reachable at (its JSONRPC interface).
    """
    return AgentCard(
        name=CV_ASSISTANT_NAME,
        description=(
            "Analyzes the gap between your resume and a specific job you name, "
            "then gives concrete suggestions to strengthen your resume — missing "
            "skills, keywords to add, bullets to reword or quantify. Use for "
            "'improve / strengthen / tailor my resume for <job>', NOT for "
            "searching or ranking jobs."
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
                id="analyze-gaps",
                name="Analyze resume gaps",
                description="Compare a resume against a chosen job and suggest concrete ways to strengthen it.",
                tags=["resume", "gaps", "suggestions"],
            )
        ],
    )
