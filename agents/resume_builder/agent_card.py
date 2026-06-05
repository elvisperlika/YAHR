"""The public :class:`AgentCard` describing the Resume Builder agent."""

from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
)
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol

AGENT_NAME = "Resume Builder"
AGENT_VERSION = "0.1.0"

_SKILL = AgentSkill(
    id="build_resume",
    name="Build structured resume",
    description=(
        "Parse resume markdown into a structured Resume object (personal info, "
        "education, work experience, projects and skills)."
    ),
    tags=["resume", "cv", "parsing", "extraction"],
    examples=[
        "Parse this resume markdown into structured fields.",
        "Extract skills and work experience from my CV.",
    ],
    input_modes=["text/markdown", "text/plain"],
    output_modes=["application/json"],
)


def build_agent_card(url: str) -> AgentCard:
    """Build the agent card advertising this agent at ``url``.

    Args:
        url: The base URL where the JSON-RPC endpoint is served
            (e.g. ``http://localhost:8001/``).
    """
    return AgentCard(
        name=AGENT_NAME,
        description=(
            "Converts a resume (Markdown) into a structured Resume object using "
            "an OpenRouter-hosted LLM."
        ),
        version=AGENT_VERSION,
        provider=AgentProvider(
            organization="YAHR", url="https://github.com/elvisperlika/YAHR"
        ),
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding=TransportProtocol.JSONRPC.value,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/markdown", "text/plain"],
        default_output_modes=["application/json"],
        skills=[_SKILL],
    )
