# Yet Another HR

YAHR is a command-line tool that acts as your personal career co-pilot. It reads your resume, searches for relevant job openings, scores them against your profile, and tells you exactly how to improve your CV to maximize your chances — all from the terminal.

## Features

- Analyze your resume and find the best job for you
- Suggest the best way to improve your resume
- Provide you with the best job opportunities based on your resume

## Architecture

Built on the A2A Protocol (an open standard for agent-to-agent communication), YAHR is composed of four specialized agents that work together under a single orchestrator:

Job Searcher Agent — queries web search APIs to discover open positions matching your background
Matching/Ranker Agent — parses your CV into a structured profile and scores each job against it
CV Assistant Agent — analyzes the gaps between your profile and the top-ranked jobs, then gives you concrete suggestions to strengthen your resume
Orchestrator Agent — ties everything together and exposes the full workflow through an intuitive CLI interface

## Getting Started

YAHR requires **Python 3.14**. Set up a virtual environment and install the
pinned dependencies:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration

The Resume Builder agent reasons through an OpenRouter-hosted LLM (an
OpenAI-compatible gateway). Provide the following environment variables, e.g.
in a `.env` file at the repository root:

```bash
API_KEY=<your-openrouter-api-key>
MODEL=<model-id, e.g. openai/gpt-4o-mini>
BASE_URL=https://openrouter.ai/api/v1
```

You can save the API key to `.env` from the CLI as well (you'll be prompted
for the key if you omit `--api-key`):

```bash
python -m cli.main setup --api-key <your-openrouter-api-key>
python -m cli.main setup        # prompts securely for the key
```

## Usage

The entry point is the Typer app `python -m cli.main`. The typical workflow is
**PDF → Markdown → structured Resume JSON**:

```bash
# 1. Convert a resume PDF to Markdown (written to output/<stem>.md)
python -m cli.main convert path/to/cv.pdf

# 2. Parse the Markdown into a structured Resume (prints JSON; --output to save)
python -m cli.main build-resume output/cv.md
```

### Commands

| Command                         | Description                                                 |
| ------------------------------- | ----------------------------------------------------------- |
| `convert <pdf>`                 | Convert a resume PDF to Markdown at `output/<stem>.md`.     |
| `build-resume <markdown>`       | Parse resume Markdown into a structured `Resume` (JSON).    |
| `serve-agent [--host] [--port]` | Run the Resume Builder as an A2A HTTP server.               |
| `setup [--api-key]` or `[-k]`   | Save the OpenRouter API key to `.env` (prompts if omitted). |
| `welcome`                       | Print a friendly greeting.                                  |

Run any command with `--help` for its full options, e.g.
`python -m cli.main build-resume --help`.

### Running the agent server

The Resume Builder is also exposed as a standalone A2A service (Starlette +
uvicorn), serving JSON-RPC and agent-card endpoints:

```bash
python -m cli.main serve-agent --host 127.0.0.1 --port 8001
python -m agents.resume_builder.server --port 8001   # equivalent, no CLI
```

## Dependencies

- MarkItDown
- Gemini models
- Typer
- Rich
- git+https://github.com/tensorflow/docs
  - ipython
  - jupyter
  - nbconvert
  - nbformat
  - nbqa
  - ruff
  - autoflake