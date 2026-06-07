# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

YAHR (Yet Another HR) is a personal HR assistant CLI that parses a resume PDF, searches for matching jobs, and suggests resume improvements.

## Environment

Python 3.14 with a local venv at `.venv/`. Always use the venv:

```bash
source .venv/bin/activate
```

## Commands

```bash
# Lint
ruff check .
ruff format .

# Clean unused imports
autoflake --remove-all-unused-imports -r .

# Lint notebooks
nbqa ruff notebooks/

# Run the test suite (no pytest dependency required)
PYTHONPATH=. python tests/test_resume_builder.py

# CLI: PDF -> Markdown -> structured Resume JSON
python -m cli.main convert path/to/cv.pdf            # writes output/<stem>.md
python -m cli.main build-resume output/resume.md     # prints/saves Resume JSON

# Run the Resume Builder A2A agent (HTTP server)
python -m cli.main serve-agent --host 127.0.0.1 --port 8001
python -m agents.resume_builder.server --port 8001   # equivalent, no CLI
```

The CLI is a `typer` app under `cli/`; `python -m cli.main` is the entry point.
Tests live in `tests/` and run standalone (a tiny built-in runner stands in for
pytest) or under pytest if it is installed.

## Architecture

Agents coordinated by an orchestrator, all driven from a CLI entry point:

- **`agents/resume_builder/`** — *implemented.* An A2A agent that turns resume
  markdown into a structured `Resume` via an OpenRouter-hosted LLM.
  - `core.py` — transport-agnostic logic: markdown → `Resume` (the
    `build_resume_from_markdown` coroutine + JSON parsing into the dataclasses).
  - `config.py` — OpenRouter settings from env (`OPENROUTER_API_KEY` required;
    `OPENROUTER_MODEL` defaults to a free model; `OPENROUTER_BASE_URL`).
  - `executor.py` — `ResumeBuilderExecutor`, the A2A `AgentExecutor`; emits the
    `Resume` as a JSON data artifact named `resume`.
  - `agent_card.py` — the public `AgentCard` (skill `build_resume`).
  - `server.py` — assembles `DefaultRequestHandlerV2` + JSON-RPC/agent-card
    routes into a Starlette app and serves it with uvicorn.
- **`agents/job_searcher.py`** — *planned.* Calls external job APIs to find open positions.
- **`agents/ranker.py`** — *planned.* Scores each job listing against the parsed CV profile.
- **`agents/orchestrator.py`** — *planned.* Coordinates the agents in sequence.
- **`cli/`** — Typer + Rich CLI. Commands live in `cli/commands/` and self-register
  by importing `app` from `cli.app` (see `cli/app.py`).

> **Important:** the installed A2A SDK is the PyPI package named `a2a`
> (`a2a-sdk`, protobuf-based — types live in `a2a.types`, i.e. `a2a.types.a2a_pb2`).
> Do **not** create a top-level `a2a/` Python package in this repo: an
> `a2a/__init__.py` at the repo root would shadow the installed SDK. Agent code
> lives under `agents/` for this reason. (The empty `a2a/` directory present in
> the working tree is harmless only because it has no `__init__.py`.)

## Key dependencies

| Package                                   | Role                                                              |
| ----------------------------------------- | ----------------------------------------------------------------- |
| `a2a-sdk`                                 | A2A protocol types + server (`a2a` package, protobuf-based)       |
| `markitdown`                              | PDF → Markdown conversion for CV parsing                          |
| `openai`                                  | LLM calls — used as the OpenRouter client via a custom `base_url` |
| `typer`                                   | CLI framework                                                     |
| `rich`                                    | Terminal output formatting                                        |
| `starlette` / `uvicorn` / `sse-starlette` | ASGI server for the A2A HTTP endpoint                             |
| `ruff` / `autoflake`                      | Linting and import cleanup                                        |

Runtime deps are pinned in `requirements.txt` (`pip install -r requirements.txt`).
