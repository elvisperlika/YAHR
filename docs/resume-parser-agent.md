Done. I built a full A2A agent that reads resume markdown and produces a structured Resume object via OpenRouter, and verified it end-to-end.

What was built

agents/resume_builder/ — the new A2A agent:
- core.py — transport-agnostic logic: build_resume_from_markdown(markdown) → Resume. Calls OpenRouter through the openai SDK (custom base_url), prompts for strict JSON, and defensively maps the result onto your models/resume.py dataclasses. Degrades gracefully when a free model rejects response_format, and robustly extracts JSON even if the model wraps it in prose/fences.
- config.py — env-driven config: OPENROUTER_API_KEY (required), OPENROUTER_MODEL (defaults to the free deepseek/deepseek-chat-v3-0324:free, overridable), OPENROUTER_BASE_URL, optional attribution headers.
- executor.py — ResumeBuilderExecutor (the A2A AgentExecutor). Accepts the markdown in the message text, a file path, or a {"markdown"|"path"} data part; emits the Resume as a JSON artifact named resume plus a summary, and fails cleanly on errors.
- agent_card.py — the public AgentCard (skill build_resume).
- server.py — wires DefaultRequestHandlerV2 + JSON-RPC/agent-card routes into a Starlette app, served by uvicorn.

CLI (cli/commands/resume.py): build-resume (parse a markdown file locally) and serve-agent (run the HTTP server).

Tests (tests/test_resume_builder.py): 7 tests, runnable without pytest. Includes a full JSON-RPC SendMessage round trip — all pass.

Deps: added starlette, uvicorn, sse-starlette (installed) and created requirements.txt (none existed). CLAUDE.md updated.

Verified

- Agent card served at /.well-known/agent-card.json (200).
- JSON-RPC SendMessage → TASK_STATE_COMPLETED with a resume JSON artifact (LLM stubbed).
- Missing API key → clean TASK_STATE_FAILED with a helpful message.
- ruff check/format clean on new code.

Two things worth flagging

1. a2a/ shadowing gotcha — the installed SDK is the package named a2a. A top-level a2a/__init__.py in this repo would shadow it, so I put the agent under agents/. Documented in CLAUDE.md. (The empty a2a/ dir in your tree is harmless only because it has no __init__.py.)
2. Clients must send the A2A-Version: 1.0 header — the SDK's request handler rejects requests without it. Real A2A client libraries set this automatically.

To run it for real: export OPENROUTER_API_KEY=... then python -m cli.main serve-agent, or python -m cli.main build-resume output/resume.md to test the parsing path directly.

I did not commit anything (changes are unstaged) — let me know if you'd like me to commit, or to add a sample A2A client script that calls the running agent.