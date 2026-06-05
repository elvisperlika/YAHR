import typer
from rich.console import Console

app = typer.Typer(add_completion=False)
console = Console()
err_console = Console(stderr=True)

from cli.commands import convert, resume, welcome  # noqa: E402, F401
