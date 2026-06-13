import httpx
import typer
from rich.table import Table

from agents.job_searcher.adzuna import MissingAdzunaCredentialsError
from agents.job_searcher.factory import (
    UnknownProviderError,
    get_provider,
    search_jobs_sync,
)
from agents.job_searcher.provider import JobPosting
from cli.app import app, console, err_console


@app.command(name="search-jobs")
def search_jobs(
    what: str = typer.Argument(..., help="Role / keywords to search for."),
    where: str = typer.Option(
        "", "--where", "-w", help="Location filter (city, region)."
    ),
    limit: int = typer.Option(
        20, "--limit", "-n", min=1, help="Maximum number of postings to return."
    ),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help="Override the configured job provider (default: JOBS_PROVIDER).",
    ),
    all_jobs: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Include postings without a disclosed salary (off by default).",
    ),
):
    """Search for open job positions via the configured provider.

    By default only postings that disclose a salary are shown; pass ``--all``
    to include the rest.
    """
    try:
        backend = get_provider(provider)
    except UnknownProviderError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    try:
        with console.status("[bold cyan]Searching jobs…[/bold cyan]", spinner="dots"):
            postings = search_jobs_sync(
                what=what,
                where=where,
                limit=limit,
                with_salary=not all_jobs,
                provider=backend,
            )
    except MissingAdzunaCredentialsError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except httpx.HTTPError as e:
        err_console.print(f"[red]Search failed:[/red] {e}")
        raise typer.Exit(code=1)

    if not postings:
        console.print(f"[yellow]No jobs found for[/yellow] '{what}'.")
        return

    console.print(_render(postings, backend.name))


def _render(postings: list[JobPosting], source: str) -> Table:
    """Lay the postings out in a Rich table."""
    table = Table(title=f"{len(postings)} jobs · {source}", title_justify="left")
    table.add_column("Title", style="bold")
    table.add_column("Company")
    table.add_column("Location")
    table.add_column("Salary")
    table.add_column("Link", style="cyan")

    for p in postings:
        table.add_row(
            p.title, p.company, p.location, _salary(p), f"[link={p.url}]🔗[/link]"
        )
    return table


def _salary(p: JobPosting) -> str:
    """Format a posting's salary range, or ``—`` when unknown."""
    lo, hi = p.salary_min, p.salary_max
    if lo and hi:
        return f"{lo:,.0f}–{hi:,.0f}"
    if lo:
        return f"{lo:,.0f}+"
    if hi:
        return f"≤{hi:,.0f}"
    return "—"
