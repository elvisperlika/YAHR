# YAHR

![YAHR](docs/image/logo.png)

**Yet Another HR** — a command-line career co-pilot. From a resume PDF it parses a structured profile, searches job listings, scores them against the profile, and suggests resume improvements. It is built on the [A2A](https://a2a-protocol.org/) protocol: specialized agents behind a single LLM-routing orchestrator.

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

The Job Searcher queries [Adzuna](https://developer.adzuna.com/) for real listings. Set your credentials to enable it; without them it falls back to canned jobs, so the rest of the pipeline still runs offline:

```bash
# .env (optional — omit to use canned jobs)
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
ADZUNA_COUNTRY=it   # two-letter country code, default 'it'
```

## Commands

| Command | What it does |
| --- | --- |
| `yahr convert <resume.pdf>` | Convert a PDF resume to clean Markdown at `output/<name>.md` — one LLM pass repairs reading order and structure. |
| `yahr serve [agent]` | Run an agent as an A2A HTTP server. Built agents: `job-searcher` (default, on `127.0.0.1:8002`) and `ranker` (`8003`). |
| `yahr ask "<query>"` | Route a natural-language query to the best running agent and stream its progress live. |
| `yahr hello [--name X]` | Sanity-check that the CLI is installed. |

### Try it

`ask` only routes to agents that are actually running and serving an Agent Card, so start one first. In different terminals run:

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
yahr ask "show me 'java developer' jobs in milano"
```

To rank jobs against your résumé, first turn your PDF into Markdown — `convert resume.pdf` writes `output/resume.md`, which `ask` picks up automatically (use `--resume <path>` for any other name). Then ask a ranking question:

```bash
# 1. résumé PDF -> output/resume.md
yahr convert resume.pdf

# 2. rank the jobs from the search above against it
yahr ask "which of these jobs best fits my resume?"
```

The orchestrator discovers the running agents, asks the LLM which one fits, and forwards the request, streaming its progress live. A plain search goes to the Job Searcher; a ranking query goes to the Ranker, which scores jobs against your résumé — reusing the jobs from a prior search, or searching first if there are none.
