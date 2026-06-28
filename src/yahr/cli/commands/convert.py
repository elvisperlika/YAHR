from pathlib import Path

from markitdown import MarkItDown
from rich.console import Console

from yahr.config import openrouter_client

console = Console()

_REFORMAT = (
    "You are given the raw text of a resume extracted from a PDF. The reading "
    "order may be scrambled (dates and locations floated out of place) and it may "
    "contain glyph artifacts like '(cid:294)'. Rewrite it as clean, well-structured "
    "GitHub-flavored Markdown: a top-level '# Name' heading, '##' section headings, "
    "and bullet lists. Restore the natural reading order and drop the artifacts. Use "
    "ONLY the information present — never invent, omit, or translate anything. Output "
    "only the Markdown."
)


def convert(resume: Path):
    """Convert a PDF resume to clean, well-formatted Markdown in output/<stem>.md.

    markitdown extracts the raw text; one OpenRouter LLM pass repairs the reading
    order, drops glyph artifacts, and applies Markdown structure.

    Args:
        resume: Path to the source resume PDF.
    """
    with console.status("[bold blue]Parsing resume…"):
        raw = MarkItDown().convert(str(resume)).text_content
        client, model = openrouter_client()
        reply = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _REFORMAT},
                {"role": "user", "content": raw},
            ],
        )
    out = Path("output") / f"{resume.stem}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(reply.choices[0].message.content or raw)
    console.print(f"[green]Wrote[/] {out}")
