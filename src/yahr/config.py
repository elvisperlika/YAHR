"""OpenRouter (OpenAI-compatible) LLM client configuration."""

import os
from pathlib import Path

from openai import OpenAI

from yahr.agents.roster import ADZUNA_MCP_ADDRESS

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemma-4-31b-it:free"

# Default job-provider MCP server: the Adzuna server's streamable-http endpoint
# (FastMCP mounts at /mcp). Point YAHR_JOBS_MCP_URL at the mock server's URL to
# run offline — the Job Searcher is agnostic to which provider sits behind it.
DEFAULT_JOBS_MCP_URL = f"{ADZUNA_MCP_ADDRESS.url}/mcp"


def load_dotenv() -> None:
    """Load KEY=VALUE pairs from a local .env into os.environ if present."""
    # ponytail: tiny .env loader, swap for python-dotenv if config grows.
    env = Path(".env")
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def openrouter_client() -> tuple[OpenAI, str]:
    """Build an OpenAI client pointed at OpenRouter and return it with the model name.

    Reads OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL from the
    environment (loading a local .env first if present).

    Returns:
        A (client, model) tuple ready for chat.completions.create.
    """
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to your environment or .env."
        )
    base_url = os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL)
    # ponytail: the OpenAI SDK appends /chat/completions itself; tolerate a
    # base_url that already includes it (common copy-paste from OpenRouter docs).
    base_url = base_url.rstrip("/").removesuffix("/chat/completions")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    return OpenAI(api_key=api_key, base_url=base_url), model


def jobs_mcp_url() -> str:
    """The job-provider MCP server URL the Job Searcher connects to.

    Reads YAHR_JOBS_MCP_URL (loading a local .env first), defaulting to the
    Adzuna server's endpoint.

    Returns:
        The streamable-http URL of the job-provider MCP server.
    """
    load_dotenv()
    return os.environ.get("YAHR_JOBS_MCP_URL", DEFAULT_JOBS_MCP_URL)


if __name__ == "__main__":
    import tempfile

    # base_url normalization: the OpenAI SDK appends /chat/completions itself, so a
    # pasted OpenRouter URL that already has it must be trimmed back to /api/v1.
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    os.environ["OPENROUTER_BASE_URL"] = "https://openrouter.ai/api/v1/chat/completions/"
    client, _ = openrouter_client()
    assert str(client.base_url).rstrip("/").endswith("/api/v1"), client.base_url
    assert "chat/completions" not in str(client.base_url), client.base_url

    # load_dotenv: parse KEY=VALUE, skip comments/blanks/no-'=' lines, strip quotes,
    # and never clobber a value already in the environment (setdefault).
    with tempfile.TemporaryDirectory() as d:
        cwd = os.getcwd()
        os.chdir(d)
        try:
            Path(".env").write_text(
                '# comment\n\nFOO=bar\nQUOTED="q u"\nNOEQ\nOPENROUTER_API_KEY=fromfile\n'
            )
            os.environ.pop("FOO", None)
            os.environ.pop("QUOTED", None)
            load_dotenv()
            assert os.environ["FOO"] == "bar"
            assert os.environ["QUOTED"] == "q u"  # surrounding quotes stripped
            assert "NOEQ" not in os.environ  # no '=' -> skipped
            assert os.environ["OPENROUTER_API_KEY"] == "test-key"  # env wins over .env
        finally:
            os.chdir(cwd)
    print("config self-check ok")
