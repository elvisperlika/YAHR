# YAHR

![YAHR](docs/image/logo.png)

**Yet Another HR** — a command-line career co-pilot. From a resume PDF it parses a structured profile, searches job listings, scores them against the profile, and suggests resume improvements. It is built on the [A2A](https://a2a-protocol.org/) protocol: specialized agents behind a single LLM-routing orchestrator.

> Status: early scaffold. The CLI, the orchestrator's A2A discovery/routing, and a mock Job Searcher agent work today. The remaining agents and the two-phase pipeline are still design-only — see [`docs/c4/`](docs/c4/) for the spec.

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
OPENROUTER_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

## Commands

| Command | What it does |
| --- | --- |
| `yahr convert <resume.pdf>` | Convert a PDF resume to Markdown at `output/<name>.md`. |
| `yahr serve [agent]` | Run an agent as an A2A HTTP server (default and only built agent: `job-searcher`, on `127.0.0.1:8002`). |
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

The orchestrator discovers the running agent, asks the LLM to route, and forwards the request — the Job Searcher is currently a mock that streams fake progress.
