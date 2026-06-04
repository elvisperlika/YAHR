# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

YAHR (Yet Another HR) is a personal HR assistant CLI that parses a resume PDF, searches for matching jobs, and suggests resume improvements. It is in early development — `agents/`, `cli/`, and `a2a/` are currently empty scaffolding.

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
```

No test runner or entry point exists yet. Once the CLI is wired up, it will be a `typer` app under `cli/`.

## Architecture

Four agents coordinated by an orchestrator, all driven from a CLI entry point:

- **`agents/pdf_parser.py`** — uses MarkItDown to convert the CV PDF to text, then extracts skills, experience, and education.
- **`agents/job_searcher.py`** — calls external job APIs (SerpAPI, Adzuna, or similar) to find open positions.
- **`agents/ranker.py`** — scores each job listing against the parsed CV profile.
- **`agents/orchestrator.py`** — coordinates the three agents above in sequence.
- **`cli/`** — Typer + Rich CLI that accepts a PDF path and drives the orchestrator.
- **`a2a/`** — agent-to-agent communication layer (purpose TBD, likely message passing between agents).

## Key dependencies

| Package | Role |
|---|---|
| `markitdown` | PDF → Markdown conversion for CV parsing |
| `openai` | LLM calls (note: README mentions Gemini but `openai` SDK is what's installed) |
| `typer` | CLI framework |
| `rich` | Terminal output formatting |
| `ruff` / `autoflake` | Linting and import cleanup |
