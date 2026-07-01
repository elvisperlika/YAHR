## Code

The package lives under `src/yahr` and splits three ways: the command-line interface, the agents, and the MCP job providers.

```text
src/yahr/
  cli/commands/      convert · serve · start · hello
  agents/
    orchestrator.py  LLM router over A2A discovery
    roster.py        agent names and addresses (one source of truth)
    models/job.py    the Job dataclass
    job_searcher/    agent_card · core · executor · providers · refine
    ranker/          agent_card · core · executor
    cv_assistant/    agent_card · core · executor
  mcp/
    adzuna/          real job board behind the search tool
    mock/            canned jobs for offline runs
  config.py          OpenRouter client and .env loading
```

Each agent is the same small set of files: `agent_card.py` for its public identity, `core.py` for the work, `executor.py` for the A2A task lifecycle, and an `__init__.py` whose `serve()` assembles the card and executor into the running server. The Job Searcher adds two files of its own, `providers.py` (the MCP client) and `refine.py` (query broadening).

The core/executor split is easiest to read in the Ranker, the smallest agent. The core is an async generator that takes a string and yields `(text, is_final)` steps, and it imports nothing from `a2a`:

```python
# agents/ranker/core.py
Step = tuple[str, bool]  # (text, is_final)

async def rank(message: str) -> AsyncIterator[Step]:
    yield "Scoring jobs against your resume", False
    client, model = openrouter_client()
    reply = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": message}],
        temperature=_TEMPERATURE, seed=_SEED,  # greedy + fixed seed
    )
    yield (reply.choices[0].message.content or "(no answer)"), True
```

The executor is the only place A2A types appear. It runs the core and turns each step into a task update, completing the task on the final one:

```python
# agents/ranker/executor.py
await updater.start_work()
async for text, is_final in core.rank(message):
    if is_final:
        await updater.complete(updater.new_agent_message([new_text_part(text)]))
    else:
        await updater.update_status(
            TaskState.TASK_STATE_WORKING,
            updater.new_agent_message([new_text_part(text + "…")]),
        )
```

The Job Searcher's core is the one piece with real control flow. Its three `break` statements are the three places the search stops, and jobs deduplicate by id through `dict.setdefault` (the per-round progress lines are elided here):

```python
# agents/job_searcher/core.py
async def _run(goal: Goal, fetch: Fetch = mock_jobs, refiner: Refiner = refine) -> AsyncIterator[Step]:
    cache: dict[str, Job] = {}
    query, calls = goal.query, 0
    for _ in range(goal.max_rounds):
        if calls >= goal.max_calls:
            break                                # spent the call budget
        for job in await fetch(query):
            cache.setdefault(job.id, job)        # dedupe by stable id
        calls += 1
        if len(cache) >= goal.target:
            break                                # found enough
        next_query = refiner(query, len(cache), goal.target)
        if next_query == query:
            break                                # cannot broaden, converged
        query = next_query
    selected = dict(list(cache.items())[: goal.target])
    yield _render(selected), True, list(selected.values())
```

The roster is the single source of truth for which agents exist and where, so a name or a port is written once:

```python
# agents/roster.py
JOB_SEARCHER_NAME = "Job Searcher Agent"
RANKER_NAME = "Ranker Agent"
CV_ASSISTANT_NAME = "CV Assistant Agent"

JOB_SEARCHER_ADDRESS = AgentAddress("127.0.0.1", 8002)
RANKER_ADDRESS = AgentAddress("127.0.0.1", 8003)
CV_ASSISTANT_ADDRESS = AgentAddress("127.0.0.1", 8007)

# The orchestrator probes exactly these for agent cards.
AGENT_URLS = [JOB_SEARCHER_ADDRESS.url, RANKER_ADDRESS.url, CV_ASSISTANT_ADDRESS.url]
```

The agent cards import these names and the `serve()` functions bind these addresses, while the orchestrator's `discover()` walks `AGENT_URLS` fetching each card. Throughout, the code leans on plain dataclasses (`Job`, `Goal`, `AgentAddress`), type hints, and `asyncio`, and every core or logic module ends with an assert-based `__main__` self-check.
