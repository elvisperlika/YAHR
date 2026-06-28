"""`yahr ask "<query>"` — route a query and show the agent's task status live."""

import asyncio
from pathlib import Path

from rich.console import Console

from yahr.agents import orchestrator

console = Console()


async def _run(query: str, resume: str | None) -> None:
    """Drive the orchestrator and render each status update as it arrives.

    Args:
        query: The user's natural-language request.
        resume: The resume Markdown to attach, or None if there is none; the
            orchestrator decides per-query whether to actually use it.
    """
    final = "[yellow](no result)[/]"
    with console.status("[bold cyan]working…[/]") as status:
        async for state, text in orchestrator.route(query, resume):
            if state == "error":
                final = f"[red]{text}[/]"
            elif state == "completed" and text:
                final = f"[green]{text}[/]"
            else:
                status.update(f"[bold cyan]{state}…[/]")
                if text:
                    console.print(f"  [dim]· {text}[/]")
    console.print(final)


def ask(query: str, resume: Path = Path("output/resume.md")):
    """Route a natural-language query to the best agent and show its progress.

    Args:
        query: What you want, e.g. "show me 'java developer' jobs in milano".
        resume: Markdown resume to attach; the orchestrator decides per-query
            whether it is useful. Ignored if the file does not exist.
    """
    text = resume.read_text() if resume.exists() else None
    asyncio.run(_run(query, text))
