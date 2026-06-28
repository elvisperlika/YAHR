"""`yahr ask "<query>"` — route a query and show the agent's task status live."""

import asyncio
from pathlib import Path

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel

from yahr.agents import orchestrator

console = Console()


def _job_card(job: dict) -> Panel:
    """Render one job as a boxed card with every field it has.

    Args:
        job: A job dict (title plus optional company/location/description/url).
    """
    meta = " · ".join(p for p in (job.get("company"), job.get("location")) if p)
    body = []
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


def _job_cards(jobs: list[dict]) -> RenderableType:
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


def ask(query: str, resume: Path = Path("output/resume.md")):
    """Route a natural-language query to the best agent and show its progress.

    Args:
        query: What you want, e.g. "show me 'java developer' jobs in milano".
        resume: Markdown resume to attach; the orchestrator decides per-query
            whether it is useful. Ignored if the file does not exist.
    """
    text = resume.read_text() if resume.exists() else None
    asyncio.run(_run(query, text))
