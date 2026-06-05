"""A2A ``AgentExecutor`` wrapping the resume-building logic."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

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

from agents.resume_builder.config import MissingAPIKeyError, OpenRouterConfig
from agents.resume_builder.core import (
    ResumeParseError,
    build_resume_from_markdown,
)

logger = logging.getLogger(__name__)

# Guard against accidentally treating a whole resume as a filename.
_MAX_PATH_LEN = 4096


def _resolve_markdown(context: RequestContext) -> str:
    """Work out the resume markdown to parse from the incoming message.

    Accepts, in priority order:

    1. A data part with ``{"markdown": "..."}`` or ``{"path": "..."}``.
    2. A text part that is a path to an existing file (its contents are read).
    3. A text part containing the markdown itself.
    """
    message = context.message
    if message is not None:
        for data in get_data_parts(message.parts):
            if isinstance(data, dict):
                if data.get("markdown"):
                    return str(data["markdown"])
                if data.get("path"):
                    return Path(str(data["path"])).read_text(encoding="utf-8")

        text = "\n".join(get_text_parts(message.parts)).strip()
    else:
        text = ""

    if text and len(text) <= _MAX_PATH_LEN and "\n" not in text:
        candidate = Path(text)
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return text


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

        try:
            markdown = _resolve_markdown(context)
        except OSError as exc:
            await updater.failed(
                updater.new_agent_message(
                    [new_text_part(f"Could not read resume input: {exc}")]
                )
            )
            return

        try:
            resume = await build_resume_from_markdown(markdown, config=self._config)
        except (MissingAPIKeyError, ResumeParseError) as exc:
            logger.warning("Resume build failed: %s", exc)
            await updater.failed(updater.new_agent_message([new_text_part(str(exc))]))
            return

        await updater.add_artifact(
            [new_data_part(asdict(resume), media_type="application/json")],
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
