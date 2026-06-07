from pathlib import Path

import typer

from cli.app import app, console, err_console

ENV_FILE = Path(".env")
KEY = "API_KEY"
BASE_URL = "BASE_URL"
MODEL = "MODEL"


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
        help="OpenRouter API key.",
    ),
    base_url: str = typer.Option(
        None,
        "--base-url",
        "-b",
        help="OpenRouter base URL (e.g. https://openrouter.ai/api/v1).",
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Model id to use (e.g. openai/gpt-4o-mini).",
    ),
):
    """Save your OpenRouter settings to the .env file.

    Each of ``API_KEY``, ``BASE_URL`` and ``MODEL`` is written only when its
    option is provided. If no option is given, the API key is prompted for.
    """
    if api_key is None and base_url is None and model is None:
        api_key = typer.prompt(KEY, hide_input=True)

    updates = [
        (KEY, api_key),
        (BASE_URL, base_url),
        (MODEL, model),
    ]

    wrote_any = False
    for key, value in updates:
        if value is None:
            continue

        value = value.strip()
        if not value:
            err_console.print(f"[red]Error:[/red] {key} must not be empty.")
            raise typer.Exit(code=1)

        updated = _upsert_env(ENV_FILE, key, value)
        verb = "Updated" if updated else "Saved"
        console.print(f"[green]{verb}[/green] {key} → {ENV_FILE}")
        wrote_any = True

    if not wrote_any:
        err_console.print("[red]Error:[/red] nothing to do; provide a value.")
        raise typer.Exit(code=1)
