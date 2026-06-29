"""`yahr serve <name>` — run a single YAHR agent (A2A) or job-provider MCP server."""

from collections.abc import Callable

import typer
from rich.console import Console

from yahr.agents import cv_assistant, job_searcher, ranker
from yahr.mcp import adzuna, mock

console = Console()

# ponytail: built servers only; grows as more land. A2A agents and the
# job-provider MCP servers share one `serve <name>` registry.
_AGENTS: dict[str, Callable[[], None]] = {
    "job-searcher": job_searcher.serve,
    "ranker": ranker.serve,
    "cv-assistant": cv_assistant.serve,
    "adzuna-mcp": adzuna.serve,
    "mock-mcp": mock.serve,
}


def serve(agent: str = typer.Argument("job-searcher")):
    """Run an A2A agent or job-provider MCP server until interrupted.

    Args:
        agent: Which server to run (e.g. 'job-searcher', 'adzuna-mcp', 'mock-mcp').
    """
    runner = _AGENTS.get(agent)
    if runner is None:
        console.print(
            f"[red]Unknown agent[/] {agent!r}. Available: {', '.join(_AGENTS)}"
        )
        raise typer.Exit(1)
    console.print(f"[green]Serving[/] {agent} …")
    runner()
