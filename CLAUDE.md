# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

YAHR (Yet Another HR) is a command-line career co-pilot: from a resume PDF it parses a structured profile, searches job listings, scores them against the profile, and suggests resume improvements. It is built on the **A2A (Agent-to-Agent) protocol** as a set of specialized agents behind a single orchestrator.

## Project status: CLI scaffold started, agents/pipeline still design-only

Real code exists only for the CLI shell: `src/yahr/cli/` (Typer + Rich) with a single `hello` command. Everything else — the agents (resume parser, job searcher, ranker, four section assistants), the two-phase pipeline, and the other CLI commands — is **still design-only**. The authoritative spec for the unbuilt parts lives in `docs/c4/*.c4` (LikeC4); treat those files as the contract when implementing, and respect that elements marked `(planned)` there are not yet built.

## Commands

Python work happens in `.venv` (Python 3.14); `ruff` lives there, `prettier` is a local npm devDependency.

```bash
.venv/bin/python -m pip install -e .   # editable install → `yahr` console script
.venv/bin/yahr hello [--name X]        # run a command (see entry-point gotcha below)
.venv/bin/ruff format .                # format Python
./node_modules/.bin/prettier --write --ignore-unknown .   # format everything else
```

There is no test suite yet — when adding one, also restore a real check (the husky pre-commit no longer guards correctness, only formatting).

## CLI source layout

- `src/yahr/cli/__init__.py` builds the Typer `app`. Commands are registered by passing plain functions to `app.command()(fn)` — the functions themselves (in `src/yahr/cli/commands/<name>.py`) carry **no** Typer decorators, keeping command logic decoupled from the app object.
- `no_args_is_help=True` makes bare `yahr` print the command list. The empty `@app.callback()` is load-bearing: without it, Typer's single-command optimization lets you run the lone command without naming it (`yahr` instead of `yahr hello`); the callback forces proper subcommand mode.

## Architecture (design, from docs/c4/)

- **`YAHR.c4`** — system context + agent containers. The orchestrator fans out over A2A to: Resume Parser, Job Searcher, Ranker, and four section assistants (summary / skills / experience / projects). External systems: OpenRouter (OpenAI-compatible LLM gateway) and a job board API (Adzuna).
- **`CLI.c4`** — the full intended CLI surface: `convert` (PDF→Markdown via markitdown), `serve <agent>` / `serve-all` (run agents as HTTP servers on ports 8001-8004), `match` (rank jobs via the running orchestrator at 127.0.0.1:8004), `setup-openrouter`, `setup-jobs-provider`, `welcome`.
- **`PIPELINE.c4`** — the two-phase runtime flow: (1) parse + search in parallel, then rank; (2) an iterative refinement loop that rewrites the weakest resume section, re-ranks against the chosen job, and keeps the rewrite only if the score rises — until no section helps or a round cap (N=5) is hit. Section assistants rewrite using only facts already in the resume; they never invent experience.

Intended stack (per the C4 `technology` tags): Python 3.14, Typer + Rich for the CLI, `a2a-sdk` for agents, Starlette/uvicorn to serve them, `httpx`, `markitdown`, and an OpenAI client pointed at OpenRouter.

Use the `likec4-dsl` skill for `.c4` syntax/CLI questions. The model spans multiple files sharing one workspace — `CLI.c4` and `PIPELINE.c4` `extend` / reference elements defined in `YAHR.c4`; don't redefine shared elements.

## Docs site

`docs/` is a Jekyll site (`docs/index.md` is the report; section bodies are still stubs). `docs/_config.yml` excludes `c4/*.c4` from the build and uses the custom layout in `docs/_layouts/default.html`.

## Tooling / gotchas

- **Pre-commit formats, it does not test.** `.husky/pre-commit` runs `ruff format .` + `prettier --write .` then `git add -u` to re-stage — so a commit can pull in formatting changes to files beyond what you staged.
- **Claude cannot commit.** `.claude/settings.json` denies `Bash(git commit*)` (plus `curl`/`wget`/`rm -rf`/force-push and reads of `.env`/`secrets`). Committing is a human action here.
