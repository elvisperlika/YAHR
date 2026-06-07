"""A2A ``AgentExecutor`` wrapping the resume-building logic."""

from __future__ import annotations

import logging
from dataclasses import asdict

from a2a.helpers.proto_helpers import (
    get_data_parts,
    get_text_parts,
    new_data_part,
    new_task_from_user_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from agents.resume_builder.config import ConfigError, OpenRouterConfig
from agents.resume_builder.core import (
    ResumeParseError,
    build_resume_from_markdown,
)

logger = logging.getLogger(__name__)


def _resolve_markdown(context: RequestContext) -> str:
    """Work out the resume markdown to parse from the incoming message.

    Accepts, in priority order:

    1. A data part with ``{"markdown": "..."}``.
    2. A text part containing the markdown itself.

    The markdown must be supplied inline. Filesystem paths are intentionally
    not honoured here: this executor can be exposed over the network, and
    reading arbitrary server-side files from a request would be an LFI hole.
    """
    message = context.message
    if message is None:
        return ""

    for data in get_data_parts(message.parts):
        if isinstance(data, dict) and data.get("markdown"):
            return str(data["markdown"])

    return "\n".join(get_text_parts(message.parts)).strip()


class ResumeBuilderExecutor(AgentExecutor):
    """Parses resume markdown into a structured Resume and returns it as JSON."""

    def __init__(self, config: OpenRouterConfig | None = None) -> None:
        # If provided, a shared config is reused across requests; otherwise each
        # request loads it from the environment (so key rotation is picked up).
        self._config = config

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # The v2 framework requires a Task to be enqueued before any status or
        # artifact update for a brand-new request.
        if context.current_task is None and context.message is not None:
            await event_queue.enqueue_event(new_task_from_user_message(context.message))

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()

        markdown = _resolve_markdown(context)

        try:
            resume = await build_resume_from_markdown(markdown, config=self._config)
        except (ConfigError, ResumeParseError) as exc:
            logger.warning("Resume build failed: %s", exc)
            await updater.failed(updater.new_agent_message([new_text_part(str(exc))]))
            return

        # raw_text just echoes the input; don't ship it back in the artifact.
        data = asdict(resume)
        data.pop("raw_text", None)
        await updater.add_artifact(
            [new_data_part(data, media_type="application/json")],
            name="resume",
        )

        name = resume.personal_info.name or "the candidate"
        summary = (
            f"Parsed resume for {name}: "
            f"{len(resume.work_experience)} role(s), "
            f"{len(resume.education)} education entr(ies), "
            f"{len(resume.projects)} project(s)."
        )
        await updater.complete(updater.new_agent_message([new_text_part(summary)]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.update_status(TaskState.TASK_STATE_CANCELED)
