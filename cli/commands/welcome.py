import typer
from rich.console import Console
from cli.app import app, console


@app.command()
def welcome():
    """Print a friendly greeting."""
    console.print("[bold green]Welcome to YAHR![/bold green]")
