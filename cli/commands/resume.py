import json
from dataclasses import asdict
from pathlib import Path

import typer

from agents.resume_builder.config import MissingAPIKeyError
from agents.resume_builder.core import (
    ResumeParseError,
    build_resume_from_markdown_sync,
)
from cli.app import app, console, err_console


@app.command(name="build-resume")
def build_resume(
    markdown: Path = typer.Argument(
        Path("output/resume.md"),
        help="Path to the resume markdown file.",
    ),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the structured Resume JSON here instead of stdout.",
    ),
):
    """Parse a resume markdown file into a structured Resume (via OpenRouter)."""
    if not markdown.is_file():
        err_console.print(f"[red]Error:[/red] File not found: {markdown}")
        raise typer.Exit(code=1)

    text = markdown.read_text(encoding="utf-8")
    try:
        with console.status(
            "[bold cyan]Building resume…[/bold cyan]", spinner="dots"
        ):
            resume = build_resume_from_markdown_sync(text)
    except MissingAPIKeyError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except ResumeParseError as e:
        err_console.print(f"[red]Parse failed:[/red] {e}")
        raise typer.Exit(code=1)

    # raw_text just echoes the input; drop it from the rendered JSON.
    data = asdict(resume)
    data.pop("raw_text", None)
    payload = json.dumps(data, indent=2, ensure_ascii=False)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        console.print(f"[green]Saved[/green] → {output}")
    else:
        console.print_json(payload)


@app.command(name="serve-agent")
def serve_agent(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8001, help="Port to bind."),
):
    """Run the Resume Builder agent as an A2A HTTP server."""
    from agents.resume_builder.server import serve

    console.print(
        f"[bold green]Resume Builder agent[/bold green] on http://{host}:{port}"
    )
    serve(host=host, port=port)
