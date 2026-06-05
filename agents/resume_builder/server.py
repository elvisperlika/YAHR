"""HTTP server for the Resume Builder A2A agent.

Wires the :class:`ResumeBuilderExecutor` into a JSON-RPC A2A endpoint plus the
well-known agent card route, and serves them with uvicorn.

Run directly::

    python -m agents.resume_builder.server --host 0.0.0.0 --port 8001

or programmatically via :func:`serve` / :func:`build_app`.
"""

from __future__ import annotations

import argparse
import logging

from a2a.server.request_handlers.default_request_handler_v2 import (
    DefaultRequestHandlerV2,
)
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.utils.constants import DEFAULT_RPC_URL
from starlette.applications import Starlette

from agents.resume_builder.agent_card import build_agent_card
from agents.resume_builder.executor import ResumeBuilderExecutor

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001


def build_app(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    rpc_url: str = DEFAULT_RPC_URL,
) -> Starlette:
    """Build the Starlette ASGI app exposing the Resume Builder agent.

    The agent card advertises the public base URL so clients can discover the
    JSON-RPC endpoint.
    """
    public_url = f"http://{host}:{port}{rpc_url}"
    agent_card = build_agent_card(public_url)

    handler = DefaultRequestHandlerV2(
        agent_executor=ResumeBuilderExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes = [
        *create_jsonrpc_routes(handler, rpc_url=rpc_url),
        *create_agent_card_routes(agent_card),
    ]
    return Starlette(routes=routes)


def serve(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    rpc_url: str = DEFAULT_RPC_URL,
) -> None:
    """Build and run the agent server with uvicorn (blocking)."""
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    app = build_app(host=host, port=port, rpc_url=rpc_url)
    logger.info(
        "Resume Builder agent: card at http://%s:%s/.well-known/agent-card.json",
        host,
        port,
    )
    uvicorn.run(app, host=host, port=port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Resume Builder A2A agent.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    args = parser.parse_args(argv)
    serve(host=args.host, port=args.port, rpc_url=args.rpc_url)


if __name__ == "__main__":
    main()
