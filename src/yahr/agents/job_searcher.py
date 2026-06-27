"""Mock Job Searcher A2A agent: real agent card, task with streamed progress.

ponytail: the executor fakes a few progress steps with sleeps instead of calling
Adzuna/an LLM — it exists to prove the Orchestrator's task tracking end-to-end.
Swap the body of execute() for the real search when the agent is built.
"""

import asyncio
import uuid

import uvicorn
from a2a.helpers import new_task, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    TaskState,
)
from a2a.utils.constants import TransportProtocol
from starlette.applications import Starlette

from yahr.agents.roster import JOB_SEARCHER_ADDRESS, AgentAddress


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


class JobSearcherExecutor(AgentExecutor):
    """Runs the search as a task, streaming progress until it completes (mock)."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Drive a task from working through to completion, publishing status.

        Args:
            context: The incoming A2A request (carries the user's query text).
            event_queue: Where the task and its status events are published.
        """
        query = context.get_user_input()
        task_id = context.task_id or uuid.uuid4().hex
        context_id = context.context_id or uuid.uuid4().hex
        if not context.current_task:
            await event_queue.enqueue_event(
                new_task(task_id, context_id, TaskState.TASK_STATE_SUBMITTED)
            )
        updater = TaskUpdater(event_queue, task_id, context_id)

        # ponytail: fake milestones with sleeps; a real search streams real ones.
        steps = [f"Querying job board for {query!r}", "Enriching the listings found"]
        await updater.start_work()
        for step in steps:
            await asyncio.sleep(0.7)
            await updater.update_status(
                TaskState.TASK_STATE_WORKING,
                updater.new_agent_message([new_text_part(step + "…")]),
            )
        await asyncio.sleep(0.7)
        await updater.complete(
            updater.new_agent_message(
                [new_text_part(f"[Job Searcher mock] Would search jobs for: {query!r}")]
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """No-op: the mock has nothing long-running to cancel.

        Args:
            context: The request whose task would be cancelled.
            event_queue: Where a cancellation event would be published.
        """
        # ponytail: nothing long-running to cancel in the mock.


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
