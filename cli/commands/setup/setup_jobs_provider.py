import typer

from cli.app import app, console, err_console
from cli.commands.setup.env_file import ENV_FILE, upsert_env

PROVIDER = "JOBS_PROVIDER"
ADZUNA_APP_ID = "ADZUNA_APP_ID"
ADZUNA_APP_KEY = "ADZUNA_APP_KEY"
ADZUNA_COUNTRY = "ADZUNA_COUNTRY"

SUPPORTED = {"adzuna"}


@app.command(name="setup-jobs-provider")
def setup_jobs_provider(
    provider: str = typer.Option(
        "adzuna",
        "--provider",
        "-p",
        help="Job-search provider to use.",
    ),
    app_id: str = typer.Option(
        None,
        "--app-id",
        help="Adzuna app id (public).",
    ),
    app_key: str = typer.Option(
        None,
        "--app-key",
        help="Adzuna app key (secret).",
    ),
    country: str = typer.Option(
        None,
        "--country",
        "-c",
        help="Default ISO country code, e.g. it, gb, us.",
    ),
):
    """Save your job-search provider settings to the .env file.

    Records ``JOBS_PROVIDER`` and the chosen provider's credentials. When no
    Adzuna option is given, the app id / app key are prompted for.
    """
    provider = provider.strip().lower()
    if provider not in SUPPORTED:
        err_console.print(
            f"[red]Error:[/red] unsupported provider '{provider}'. "
            f"Supported: {', '.join(sorted(SUPPORTED))}."
        )
        raise typer.Exit(code=1)

    if app_id is None and app_key is None and country is None:
        app_id = typer.prompt(ADZUNA_APP_ID)
        app_key = typer.prompt(ADZUNA_APP_KEY, hide_input=True)

    updates = [
        (PROVIDER, provider),
        (ADZUNA_APP_ID, app_id),
        (ADZUNA_APP_KEY, app_key),
        (ADZUNA_COUNTRY, country),
    ]

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
