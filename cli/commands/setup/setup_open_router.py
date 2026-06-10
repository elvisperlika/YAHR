import typer

from cli.app import app, console, err_console
from cli.commands.setup.env_file import ENV_FILE, upsert_env

KEY = "API_KEY"
BASE_URL = "BASE_URL"
MODEL = "MODEL"


@app.command(name="setup-openrouter")
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

        updated = upsert_env(ENV_FILE, key, value)
        verb = "Updated" if updated else "Saved"
        console.print(f"[green]{verb}[/green] {key} → {ENV_FILE}")
        wrote_any = True

    if not wrote_any:
        err_console.print("[red]Error:[/red] nothing to do; provide a value.")
        raise typer.Exit(code=1)
