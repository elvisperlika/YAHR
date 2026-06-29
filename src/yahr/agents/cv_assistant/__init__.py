"""CV Assistant A2A agent: analyses the gap between the resume and a chosen job.

Decoupled across the package (mirrors ranker):
    agent_card.py -- the public Agent Card (identity, skills).
    executor.py   -- the A2A task lifecycle (streams progress, completes).
    core.py       -- the actual gap analysis (one LLM call), free of A2A types.

Public API: serve() wires the three together into a running HTTP server.
"""

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from yahr.agents.cv_assistant.agent_card import agent_card
from yahr.agents.cv_assistant.executor import CVAssistantExecutor
from yahr.agents.roster import CV_ASSISTANT_ADDRESS, AgentAddress


def serve(
    host: str = CV_ASSISTANT_ADDRESS.ip,
    port: int = CV_ASSISTANT_ADDRESS.port,
) -> None:
    """Run the CV Assistant as an A2A HTTP server until interrupted.

    Args:
        host: Interface to bind. Defaults to the registered address's host.
        port: TCP port to listen on. Defaults to the registered address's port.
    """
    address = AgentAddress(host, port)
    card = agent_card(address.url)
    handler = DefaultRequestHandler(
        agent_executor=CVAssistantExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = Starlette(
        routes=create_agent_card_routes(card) + create_jsonrpc_routes(handler, "/"),
    )
    uvicorn.run(app, host=host, port=port)
