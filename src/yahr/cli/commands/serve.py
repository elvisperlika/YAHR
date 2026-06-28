"""`yahr serve <agent>` — run a single YAHR agent as an A2A HTTP server."""

import typer
from rich.console import Console

from yahr.agents import job_searcher, ranker

console = Console()

# ponytail: built agents only; grows as more land.
_AGENTS = {"job-searcher": job_searcher.serve, "ranker": ranker.serve}


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
