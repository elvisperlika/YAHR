import typer
from rich.console import Console

HELP = """
YAHR (Yet Another HR) — your personal career co-pilot in the terminal.

Parse a resume PDF into a structured profile, search for matching jobs, and get
concrete suggestions to improve your CV.

[bold]Typical workflow[/bold]

  1. yahr setup                            configure your OpenRouter key / model
  2. yahr convert resume.pdf               PDF -> output/resume.md
  3. yahr build-resume output/resume.md    Markdown -> structured Resume JSON

Run [cyan]yahr COMMAND --help[/cyan] for details on any command.
Docs: https://github.com/elvisperlika/YAHR
"""

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    help=HELP,
)
console = Console()
err_console = Console(stderr=True)

from cli.commands import convert, resume, welcome  # noqa: E402, F401
from cli.commands.setup import setup_jobs_provider, setup_open_router  # noqa: E402, F401
