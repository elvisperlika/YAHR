from pathlib import Path

import typer
from markitdown import MarkItDown, FileConversionException, UnsupportedFormatException
from rich.console import Console

app = typer.Typer(add_completion=False)
console = Console()
err_console = Console(stderr=True)


@app.command()
def convert(
    pdf: Path = typer.Argument(..., help="Path to the PDF file to convert"),
):
    """Convert a PDF to Markdown."""
    if not pdf.exists():
        err_console.print(f"[red]Error:[/red] File not found: {pdf}")
        raise typer.Exit(code=1)

    if not pdf.is_file():
        err_console.print(f"[red]Error:[/red] Not a file: {pdf}")
        raise typer.Exit(code=1)

    try:
        md = MarkItDown()
        result = md.convert(pdf)
        markdown = result.text_content
    except UnsupportedFormatException:
        err_console.print(f"[red]Error:[/red] Unsupported file format: {pdf.suffix}")
        raise typer.Exit(code=1)
    except FileConversionException as e:
        err_console.print(f"[red]Error:[/red] Conversion failed: {e}")
        raise typer.Exit(code=1)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output = output_dir / (pdf.stem + ".md")

    output.write_text(markdown, encoding="utf-8")
    console.print(f"[green]Saved[/green] → {output}")


@app.command()
def welcome():
    """Print a friendly greeting."""
    console.print("[bold green]Welcome to YAHR![/bold green]")


def main():
    app()


if __name__ == "__main__":
    main()
