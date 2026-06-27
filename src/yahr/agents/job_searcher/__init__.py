"""Job Searcher A2A agent: discovers open positions (mock).

Decoupled across the package:
    agent_card.py -- the public Agent Card (identity, skills).
    executor.py   -- the A2A task lifecycle (streams progress, completes).
    core.py       -- the actual search work, free of any A2A types.

Public API: serve() wires the three together into a running HTTP server.
"""

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette

from yahr.agents.job_searcher.agent_card import agent_card
from yahr.agents.job_searcher.executor import JobSearcherExecutor
from yahr.agents.roster import JOB_SEARCHER_ADDRESS, AgentAddress


def serve(
    host: str = JOB_SEARCHER_ADDRESS.ip,
    port: int = JOB_SEARCHER_ADDRESS.port,
) -> None:
    """Run the Job Searcher as an A2A HTTP server until interrupted.

    Args:
        host: Interface to bind. Defaults to the registered address's host.
        port: TCP port to listen on. Defaults to the registered address's port.
    """
    address = AgentAddress(host, port)
    card = agent_card(address.url)
    handler = DefaultRequestHandler(
        agent_executor=JobSearcherExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = Starlette(
        routes=create_agent_card_routes(card) + create_jsonrpc_routes(handler, "/"),
    )
    uvicorn.run(app, host=host, port=port)
