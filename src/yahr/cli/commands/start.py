"""`yahr start` — chat with the agents, or `yahr start "<query>"` for a one-shot run."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel

from yahr.agents import orchestrator

console = Console()


def _job_card(job: dict[str, str]) -> Panel:
    """Render one job as a boxed card with every field it has.

    Args:
        job: A job dict (title plus optional company/location/description/url).
    """
    parts: list[str] = []
    if company := job.get("company"):
        parts.append(company)
    if location := job.get("location"):
        parts.append(location)
    if salary := job.get("salary"):
        parts.append(f"[green]{salary}[/]")
    meta = " · ".join(parts)
    body: list[str] = []
    if meta:
        body.append(f"[bold]{meta}[/]")
    if job.get("description"):
        body.append(job["description"])
    if job.get("url"):
        body.append(f"[link={job['url']}]Apply ↗[/link]")
    return Panel(
        "\n\n".join(body) or "[dim]—[/]",
        title=f"[bold cyan]{job.get('title', '(untitled)')}[/]",
        title_align="left",
        border_style="cyan",
        padding=(1, 2),
    )


def _job_cards(jobs: list[dict[str, str]]) -> RenderableType:
    """Stack the found jobs as boxed cards under a count header.

    Args:
        jobs: The structured jobs to render.
    """
    if not jobs:
        return "[yellow]No jobs found.[/]"
    header = f"[bold green]{len(jobs)} jobs found[/]"
    return Group(header, "", *(_job_card(job) for job in jobs))


async def _run(query: str, resume: str | None) -> None:
    """Drive the orchestrator and render each status update as it arrives.

    Args:
        query: The user's natural-language request.
        resume: The resume Markdown to attach, or None if there is none; the
            orchestrator decides per-query whether to actually use it.
    """
    final: RenderableType = "[yellow](no result)[/]"
    with console.status("[bold cyan]working…[/]") as status:
        async for state, text, data in orchestrator.route(query, resume):
            if state == "error":
                final = f"[red]{text}[/]"
            elif state == "completed" and data:
                # Structured jobs -> boxed cards.
                final = _job_cards(data)
            elif state == "completed" and text:
                # Any other agent result (e.g. the ranker) -> rendered Markdown.
                final = Markdown(text)
            else:
                status.update(f"[bold cyan]{state}…[/]")
                if text:
                    console.print(f"  [dim]· {text}[/]")
    console.print(final)


def _read(resume: Path) -> str | None:
    """Read the resume Markdown fresh, or None if the file is absent.

    Args:
        resume: Path to the Markdown resume.
    """
    return resume.read_text() if resume.exists() else None


def start(query: str = typer.Argument(None), resume: Path = Path("output/resume.md")):
    """Chat with the agents, or answer one query and exit if given.

    With no query, opens a REPL: type a request, see the result, repeat — the
    orchestrator caches jobs and resume across turns, so a search → rank → tailor
    flow carries over. Ctrl-D or 'exit' quits; Ctrl-C cancels the current turn.

    Args:
        query: What you want, e.g. "show me 'java developer' jobs in milano".
            Omit it to start the chat.
        resume: Markdown resume to attach; the orchestrator decides per-query
            whether it is useful. Re-read each turn, ignored if absent.
    """
    if query:
        asyncio.run(_run(query, _read(resume)))
        return

    console.print("[dim]YAHR — ask anything. Ctrl-D or 'exit' to quit.[/]")
    while True:
        try:
            q = console.input("[bold green]> [/]").strip()
        except EOFError:
            console.print()
            return
        except KeyboardInterrupt:
            console.print()
            continue
        if q in ("exit", "quit"):
            return
        if not q:
            continue
        try:
            # ponytail: new event loop + agent re-discovery per turn; fine for a
            # CLI. Hoist the loop/httpx client into the REPL if turns feel slow.
            asyncio.run(_run(q, _read(resume)))
        except KeyboardInterrupt:
            console.print("\n[dim]cancelled[/]")
