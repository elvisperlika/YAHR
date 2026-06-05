"""Resume Builder A2A agent.

Reads resume markdown (e.g. the output of ``yahr convert``) and uses an
OpenRouter-hosted LLM to produce a structured :class:`~models.resume.Resume`.

Public surface:

- :func:`agents.resume_builder.core.build_resume_from_markdown` — the async
  parsing primitive.
- :class:`agents.resume_builder.executor.ResumeBuilderExecutor` — the A2A
  ``AgentExecutor`` wrapping that primitive.
- :func:`agents.resume_builder.server.build_app` /
  :func:`agents.resume_builder.server.serve` — the HTTP server entry points.
"""

from agents.resume_builder.core import (
    ResumeParseError,
    build_resume_from_markdown,
)

__all__ = ["ResumeParseError", "build_resume_from_markdown"]
