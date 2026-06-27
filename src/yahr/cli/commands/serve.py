"""`yahr serve <agent>` — run a single YAHR agent as an A2A HTTP server."""

import typer
from rich.console import Console

from yahr.agents import job_searcher

console = Console()

# ponytail: only the built agent is registered; grows as agents land.
_AGENTS = {"job-searcher": job_searcher.serve}


def serve(agent: str = typer.Argument("job-searcher")):
    """Run an A2A agent server until interrupted.

    Args:
        agent: Which agent to serve. Currently only 'job-searcher' is built.
    """
    runner = _AGENTS.get(agent)
    if runner is None:
        console.print(
            f"[red]Unknown agent[/] {agent!r}. Available: {', '.join(_AGENTS)}"
        )
        raise typer.Exit(1)
    console.print(f"[green]Serving[/] {agent} …")
    runner()
