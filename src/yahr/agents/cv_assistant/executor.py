"""The CV Assistant's A2A executor: drives the task lifecycle, relaying core.analyze."""

import uuid

from a2a.helpers import new_task, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState
from rich.console import Console

from yahr.agents.cv_assistant import core

# ponytail: this agent's own server-side log (its process, not the CLI client).
console = Console()


class CVAssistantExecutor(AgentExecutor):
    """Runs core.analyze as an A2A task, streaming progress until it completes."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Drive a task from working through to completion, publishing status.

        Args:
            context: The incoming A2A request (carries the orchestrator's bundle:
                request + found jobs + optional resume).
            event_queue: Where the task and its status events are published.
        """
        message = context.get_user_input()
        task_id = context.task_id or uuid.uuid4().hex
        context_id = context.context_id or uuid.uuid4().hex
        if not context.current_task:
            await event_queue.enqueue_event(
                new_task(task_id, context_id, TaskState.TASK_STATE_SUBMITTED)
            )
        updater = TaskUpdater(event_queue, task_id, context_id)

        console.log(f"[bold cyan]analyze[/] {message.splitlines()[0]!r}")
        await updater.start_work()
        async for text, is_final in core.analyze(message):
            if is_final:
                console.log(f"[bold green]done[/] {text.splitlines()[0]}")
                await updater.complete(updater.new_agent_message([new_text_part(text)]))
            else:
                console.log(f"  [dim]·[/] {text}")
                await updater.update_status(
                    TaskState.TASK_STATE_WORKING,
                    updater.new_agent_message([new_text_part(text + "…")]),
                )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """No-op: a single LLM call has nothing long-running to cancel.

        Args:
            context: The request whose task would be cancelled.
            event_queue: Where a cancellation event would be published.
        """
        # ponytail: nothing long-running to cancel in a single LLM call.
