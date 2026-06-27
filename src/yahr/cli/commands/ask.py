"""`yahr ask "<query>"` — route a query and show the agent's task status live."""

import asyncio

from rich.console import Console

from yahr.agents import orchestrator

console = Console()


async def _run(query: str) -> None:
    """Drive the orchestrator and render each status update as it arrives.

    Args:
        query: The user's natural-language request.
    """
    final = "[yellow](no result)[/]"
    with console.status("[bold cyan]working…[/]") as status:
        async for state, text in orchestrator.route(query):
            if state == "error":
                final = f"[red]{text}[/]"
            elif state == "completed" and text:
                final = f"[green]{text}[/]"
            else:
                status.update(f"[bold cyan]{state}…[/]")
                if text:
                    console.print(f"  [dim]· {text}[/]")
    console.print(final)


def ask(query: str):
    """Route a natural-language query to the best agent and show its progress.

    Args:
        query: What you want, e.g. "show me 'java developer' jobs in milano".
    """
    asyncio.run(_run(query))
