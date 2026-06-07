from pathlib import Path

import typer

from cli.app import app, console, err_console

ENV_FILE = Path(".env")
KEY = "API_KEY"


def _upsert_env(path: Path, key: str, value: str) -> bool:
    """Set ``key=value`` in the env file at ``path``.

    Existing lines for other keys are preserved. Returns ``True`` if the key was
    already present (and updated), ``False`` if it was newly added.
    """
    line = f"{key}={value}"

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()

    found = False
    for i, current in enumerate(lines):
        stripped = current.lstrip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            lines[i] = line
            found = True
            break

    if not found:
        lines.append(line)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return found


@app.command()
def setup(
    api_key: str = typer.Option(
        None,
        "--api-key",
        "-k",
        help="OpenRouter API key. Prompted for if omitted.",
    ),
):
    """Save your OpenRouter API key to the .env file."""
    if not api_key:
        api_key = typer.prompt(KEY, hide_input=True)

    api_key = api_key.strip()
    if not api_key:
        err_console.print("[red]Error:[/red] API key must not be empty.")
        raise typer.Exit(code=1)

    updated = _upsert_env(ENV_FILE, KEY, api_key)
    verb = "Updated" if updated else "Saved"
    console.print(f"[green]{verb}[/green] {KEY} → {ENV_FILE}")
