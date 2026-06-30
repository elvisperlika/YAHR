# YAHR

![YAHR](docs/image/logo.png)

**Yet Another HR**: a command-line career co-pilot. From a resume PDF it parses a structured profile, searches job listings, scores them against the profile, and suggests resume improvements. It is built on the [A2A](https://a2a-protocol.org/) protocol: specialized agents behind a single LLM-routing orchestrator. Job boards sit behind [MCP](https://modelcontextprotocol.io/): the Job Searcher calls one generic `search` tool, so a provider is a server URL, not agent code.

## Getting Started

YAHR requires **Python 3.14**. Set up a virtual environment and install the project. Installing it (`pip install -e .`) registers the `yahr` command so you can call it directly from the terminal:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e .
```

After this, `yahr` is on your `PATH` (whenever the venv is active):

```bash
yahr --help
```

## Configuration

The orchestrator uses an LLM (via [OpenRouter](https://openrouter.ai/), OpenAI-compatible) to pick which agent should handle a query. Set your key in the environment or a local `.env` file:

```bash
# .env
OPENROUTER_API_KEY=sk-or-...
# optional overrides
OPENROUTER_MODEL=google/gemma-4-31b-it:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

The Job Searcher does not call a job board directly. It connects to a job-provider MCP server that exposes a generic `search` tool, so the same agent works against any provider. Two servers ship with YAHR: an Adzuna server ([adzuna-mcp](https://developer.adzuna.com/)) that returns real listings, and a mock server (`mock-mcp`) that returns canned jobs offline. The searcher connects to whatever `YAHR_JOBS_MCP_URL` points at, defaulting to the Adzuna server.

Adzuna needs credentials. Set them to get real listings:

```bash
# .env
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
ADZUNA_COUNTRY=it   # two-letter country code, default 'it'
```

No credentials? Point the searcher at the mock server instead and run that one (next section):

```bash
# .env
YAHR_JOBS_MCP_URL=http://127.0.0.1:8006/mcp
```

## Commands

| Command | What it does |
| --- | --- |
| `yahr convert <resume.pdf>` | Convert a PDF resume to clean Markdown at `output/<name>.md` — one LLM pass repairs reading order and structure. |
| `yahr serve [name]` | Run an A2A agent or a job-provider MCP server. A2A agents: `job-searcher` (default, `127.0.0.1:8002`), `ranker` (`8003`). MCP providers: `adzuna-mcp` (`8005`), `mock-mcp` (`8006`). |
| `yahr start [query]` | With no query, opens a chat REPL: type a request, read the result, type the next one. Pass a query to run it once and exit. Either way it routes to the best running agent and streams progress live. |
| `yahr hello [--name X]` | Sanity-check that the CLI is installed. |

### Try it

`start` only routes to agents that are actually running and serving an Agent Card, so run one first. The Job Searcher also needs a job-provider MCP server up, since that is where it gets its listings. In different terminals run:

```bash
# Start a job-provider MCP server (Adzuna; swap for mock-mcp to run offline)
yahr serve adzuna-mcp
```

```bash
# Start the Job Searcher agent
yahr serve job-searcher
```

```bash
# Start the Ranker agent
yahr serve ranker
```

In another:

```bash
yahr start "show me 'java developer' jobs in milano"
```

To rank jobs against your résumé, first turn your PDF into Markdown — `convert resume.pdf` writes `output/resume.md`, which `start` picks up automatically (use `--resume <path>` for any other name). Then ask a ranking question:

```bash
# 1. résumé PDF -> output/resume.md
yahr convert resume.pdf

# 2. rank the jobs from the search above against it
yahr start "which of these jobs best fits my resume?"
```

The orchestrator discovers the running agents, asks the LLM which one fits, and forwards the request, streaming its progress live. A plain search goes to the Job Searcher; a ranking query goes to the Ranker, which scores jobs against your résumé, reusing the jobs from a prior search or searching first if there are none.

Run `yahr start` with no query to open the REPL instead of doing a one-shot run. You type a request, read the result, then type the next one. The orchestrator keeps the jobs and résumé from earlier turns, so you can search, then rank, then ask for résumé tweaks without repeating yourself. Type `exit` or press Ctrl-D to quit; Ctrl-C cancels the current turn.
