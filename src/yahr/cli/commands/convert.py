from pathlib import Path

from markitdown import MarkItDown
from rich.console import Console

console = Console()


def convert(resume: Path):
    """Convert a PDF resume to Markdown, written to output/<stem>.md.

    Args:
        resume: Path to the source resume PDF.
    """
    out = Path("output") / f"{resume.stem}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(MarkItDown().convert(str(resume)).text_content)
    console.print(f"[green]Wrote[/] {out}")
