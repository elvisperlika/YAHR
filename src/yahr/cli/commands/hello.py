from rich.console import Console
from rich.panel import Panel

console = Console()


def hello(name: str = "there"):
    """Print a pretty hello message."""
    console.print(
        Panel.fit(
            f"[cyan]Welcome to YAHR — your career co-pilot.[/]",
        )
    )
