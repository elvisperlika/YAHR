# YAHR

![YAHR](image/logo.png)

Elvis Perlika

<elvis.perlika@studio.unibo.it>

## Abstract

YAHR (Yet Another HR) is a command-line tool that automates the job search from start to finish. It takes a resume in PDF form, converts it into a structured text profile, searches for matching open positions, scores each one against the candidate's background, and suggests concrete edits to the resume to better fit a chosen position. Everything happens in the terminal.

YAHR runs on the A2A (Agent-to-Agent) protocol, an open standard for communication between agents. Converting the resume is a separate command-line step; the rest of the work is split across three agents behind a single orchestrator. The Job Searcher finds openings, the Ranker scores them against the profile, and the CV Assistant compares the resume against a specific job and reports what to improve. The orchestrator reads each request, picks the agent that fits, and forwards the work. This report explains why YAHR exists, how it is built, and how the A2A protocol keeps its agents modular and loosely coupled.

## Domain

YAHR works in the domain of the job search: the process a person goes through to find work that fits them and to present themselves well enough to be called for an interview. Done by hand, this is slow, repetitive work. A candidate has to find openings across several sites, read each posting, judge how well it matches their background, and then decide whether and how to adjust their resume for the roles worth applying to. One resume rarely fits every posting equally well, so the tailoring has to be redone for each role.

YAHR treats this as a single-user problem. The only actor is the candidate, who runs the tool locally from the terminal and supplies one resume. There is no recruiter, no employer, and no shared account: every run is one person looking for work on their own machine. Keeping the domain this small lets the system treat the candidate's resume as the single source of truth about their background.

## Core Concepts

- Resume (or CV): the candidate's background, and the input to everything else. YAHR holds it as structured Markdown (a `# Name` heading, `##` sections, and bullets) produced by converting the source PDF. It is the only evidence the system may reason from; nothing reads in outside facts or invents experience that is not written down.
- Job (open position): one posting found for the candidate. Each has a stable id (used to drop duplicates across searches), a title, the hiring company, a location, the posting body, a link to apply, and, when listed, the gross annual salary. The posting body is the main text the system matches against.
- Query: what the candidate is looking for, in plain language. It can name a role and constraints such as location, salary, or contract type, and it can ask for a set number of results, as in "find 3 java jobs in Milan".
- Fit (score): how well a job matches the resume, on a scale from 0 to 100. Fit is judged on overlap: shared skills first, then relevant experience and seniority, then the role and domain, and finally any constraints the candidate stated.
- Gap: for one chosen job, a requirement the posting asks for that the resume does not clearly show. A gap is either something the candidate already has but worded poorly (reword) or something genuinely missing that they would need to acquire. The gap analysis pairs these with concrete edits to strengthen the resume for that specific job.

## Workflow

A full run moves through the domain in five stages. The PDF resume is converted into the Markdown profile. The candidate states a query. The system searches external job sources and gathers the matching openings. It scores each opening against the resume and ranks them best first. Finally, for a role the candidate cares about, it compares the resume against that posting and reports the gaps together with suggested edits. The candidate stays in control the whole way through: YAHR finds, scores, and advises, but it never applies on the candidate's behalf and never edits the resume itself.

## Design

YAHR is built on A2A (Agent-to-Agent), an open protocol that lets independent agents talk to each other over HTTP. The work is split across one orchestrator and three specialized agents, each running as its own A2A server on its own port and doing a single job. The orchestrator sits in front of all three, routing each request to the agent that fits and streaming the result back to the terminal.

The agents know nothing about each other or about the orchestrator. An agent answers A2A requests and returns a result, and that is all. This is what keeps the system loosely coupled. A new agent comes online by starting its server and serving an agent card, and the orchestrator finds it the next time it looks; nothing else has to change. The job boards sit one layer further out, behind MCP (Model Context Protocol), which keeps the job providers swappable too.

Two choices run through every agent. The first is that each agent keeps its protocol layer apart from its work: a thin executor drives the A2A task while a protocol-free core does the actual searching, scoring, or analysis. No A2A type reaches the core, so the core runs and can be checked offline without a server. The second is that the agents that reason over the resume, the Ranker and the CV Assistant, are pinned to greedy, seeded sampling (temperature 0 and a fixed seed) so the same input produces the same output from one run to the next. The orchestrator's routing call is pinned the same way, so a given query routes to the same agent every time. This determinism is best effort: it holds only as far as the model provider honors the seed.

### A2A Protocol

A2A gives YAHR three things it would otherwise have to build: a way to discover an agent and read its capabilities, one uniform shape for giving work to any agent and reading the result, and a streaming channel for following that work while it runs. YAHR uses a subset of the protocol through the Python `a2a-sdk`.

Every agent publishes an Agent Card, a small JSON document that states its identity (`name`, `description`, `version`), its service `url`, the `capabilities` it supports (streaming among them), the media types it accepts, and a list of `skills`. The card is the unit of discovery and capability negotiation, the thing a client reads before it sends anything. A2A allows three ways to find one: a well-known URI (`https://{host}/.well-known/agent-card.json`, following RFC 8615), a curated registry, or direct configuration. YAHR combines the last two. The roster is the direct configuration, a fixed list of host and port pairs, and the orchestrator resolves the card at each one's well-known URI. Nothing about an agent is hard-coded into the orchestrator: the description and skills it routes on come off the live card.

A2A defines three transport bindings: JSON-RPC 2.0, gRPC, and HTTP with JSON (REST). An agent may offer any of them, and its card's `url` says where to reach it. YAHR's agents speak JSON-RPC 2.0 over HTTP, and the orchestrator's client speaks the same binding.

A request is a Message: a `role` (`user` or `agent`), a `messageId`, an optional `taskId` and `contextId`, and a list of Parts. A Part holds exactly one kind of content; YAHR uses two, a text part and a data part that carries arbitrary JSON. When an agent takes on real work it answers with a Task rather than a lone message. A Task has its own `id`, a `status`, a `history` of messages, and a list of Artifacts. An Artifact is the task's output, again a bundle of Parts. A2A uses `contextId` to group several tasks into one conversation; YAHR leaves that continuity to the orchestrator's cache, so every request is a fresh task.

A Task moves through a fixed set of states. It begins `submitted` (accepted and queued), turns to `working` while the agent runs, and finishes in one of the terminal states `completed`, `failed`, `canceled`, or `rejected`. Two more states, `input-required` and `auth-required`, let an agent pause for something it needs before going on. YAHR's tasks are short and stay on the happy path: `submitted`, then `working`, then `completed`. On the server each agent's executor drives these transitions through a `TaskUpdater`, and the orchestrator turns the protocol's state names back into the plain lowercase labels it streams to the terminal.

Because the agents' cards advertise streaming, the orchestrator uses the streaming method (`message/stream`) and receives Server-Sent Events instead of a single reply. Every event is one of four kinds: the opening Task, a plain Message, a status-update event (a state change with an optional message), or an artifact-update event (a new or extended Artifact). The orchestrator handles all four: it lifts the structured jobs out of an artifact-update event, turns status-update events into the progress lines the CLI prints, and treats the status-update that reaches `completed`, or a final Message, as the finished result.

A2A defines more of a surface than YAHR uses. There are methods to fetch a task's current state, cancel a running task, resubscribe to a task's event stream after a dropped connection, and register webhooks for push notifications. YAHR needs none of them: its tasks finish in seconds with the CLI watching the stream live, so the agents implement cancel as a no-op and never register for push notifications.

### Component Diagram

The running system is a single CLI process and the servers it reaches over the network. The CLI is the only thing the candidate starts directly, and the orchestrator runs inside it. The orchestrator holds no agent logic of its own; it discovers agents, routes a query to one of them, and relays the answer.

Routing happens on every query and rides on that discovery. The orchestrator fetches the live card from each endpoint in the roster, drops any that is down or serves no card, and hands the cards it has and the query to an LLM that picks the single agent to handle it, or answers that none fits. Only a running agent can be chosen.

Once an agent is chosen, the orchestrator forwards the query over A2A and streams the task's status back to the CLI while the agent works. The Job Searcher is the only agent that reaches outside YAHR: it is an MCP client to a job-provider server, which is in turn a client to the job board's HTTP API. The Ranker and the CV Assistant call the LLM through OpenRouter and nothing else.

The Job Searcher's jobs come back to the orchestrator as an A2A artifact, and the orchestrator does two things with them: it forwards them to the CLI to render, and it caches them. A later ranking or resume question reads the cache instead of searching again, and searches afresh only when the cache is empty. The resume is cached the same way, so a follow-up question has both the jobs and the resume even when the candidate typed neither into it.

The two MCP job servers, Adzuna and the offline mock, are deliberately left out of the roster. They are MCP servers, not A2A agents, and the orchestrator must never route a query to them. Only the Job Searcher reaches them, and only as an MCP client.

#### CLI Architecture

The CLI is a Typer application that renders with Rich, and it exposes four commands. `convert` turns a resume PDF into the Markdown profile: markitdown extracts the raw text, then one LLM pass repairs the reading order and applies Markdown structure. `serve` runs one server until interrupted, either an A2A agent (`job-searcher`, `ranker`, `cv-assistant`) or a job-provider MCP server (`adzuna-mcp`, `mock-mcp`). `start` is the main command: given a query it answers once and exits, and with no query it opens a chat REPL. `hello` just checks that the CLI is installed.

Today that orchestrator runs in-process inside `start`; a standalone one on its own port is planned but not yet built, and its port is already reserved. For each request, `start` reads the resume file if it is there, passes the query and resume to the orchestrator, and renders what streams back: found jobs as boxed cards, any other agent reply as Markdown, and the intermediate status lines as the agent works. In the REPL those caches carry across turns, so a search, a "which of these fits me?" question, and a "what should I fix for the Acme role?" question become one conversation instead of three from-scratch runs.

Agent names and addresses live in one place, the roster, and both the running servers and the orchestrator's discovery list derive from it. A name or a port cannot drift between the agent that advertises it and the orchestrator that looks for it.

#### Job Searcher Agent

The Job Searcher turns a natural-language query into a list of open positions. It never calls a job board directly. It connects to whatever MCP server its configured URL points at and calls that server's generic `search` tool, so Adzuna, the bundled mock, or any future source is just a different URL.

The search is a goal-seeking loop, not a single call. It fetches jobs for the query, dedupes them by id into a running set, and checks whether it has enough. If not, it broadens the query and searches again. Broadening is LLM-first: the model offers a synonym, an adjacent title, or a wider location within the same country, while keeping the constraints the candidate stated. If the model is unreachable or returns junk, a deterministic fallback drops one qualifier (such as "senior") or the trailing word, so the loop always moves forward. It stops on the first of three conditions: it has as many jobs as the query asked for (a "find 3 jobs" count, or a default of five), the query can no longer be broadened and has converged, or it hits its budget of search rounds and fetch calls. The budget exists because the real provider is a paid, rate-limited API.

The result leaves the agent in two forms. The structured jobs go out as the `jobs` artifact. The same jobs, rendered as Markdown, are the readable result the CLI shows and the Ranker later reads.

#### Ranker Agent

The Ranker scores the found jobs against the resume and answers the candidate's question in a single LLM call. The orchestrator bundles three things into that call: the question, the jobs, and the resume. The prompt fixes the Fit rubric so the scoring stays consistent: each job gets a score from 0 to 100, the list is ranked best first, and ties break by the order the jobs arrived in, never at random. The Ranker judges only from the text it is given, so a requirement the resume does not mention counts as not met rather than a guess.

#### CV Assistant Agent

The CV Assistant takes one job the candidate names and reports how to strengthen the resume for it. As with the Ranker, it works from a bundle of the request, the jobs, and the resume in a single LLM call. It first picks the single target job by matching the title or company in the request against the postings, and falls back to the first posting when the request names none. Then it writes two sections: a Gaps section listing what the posting asks for that the resume does not clearly show, and a Suggestions section of concrete edits.

Each gap is marked REWORD, when the resume already states the fact and only needs better wording, or ACQUIRE, when it is genuinely missing. The agent stays advisory: it may flag skills the resume lacks, but it never rewrites the resume, and it credits the candidate with a strength only when that fact is actually written in the resume.

### Ranking Query Walkthrough

A ranking query pulls the pieces together. Say the candidate has already converted a resume and run a search, and now asks which of the jobs fits best:

1. CLI → Orchestrator: the query, with the resume read from `output/resume.md`.
2. Orchestrator → OpenRouter: a seeded routing call asking which agent fits. It names the Ranker.
3. Orchestrator: load the jobs from the cache the earlier search left, and call the Job Searcher first only if the cache is empty.
4. Orchestrator → Ranker: one A2A message bundling the question, those jobs, and the resume.
5. Ranker → OpenRouter: a single seeded call that scores each job against the resume and writes the ranked answer, while a `working` status streams back.
6. Ranker → Orchestrator: the task reaches `completed` with the ranked list and the answer.
7. Orchestrator → CLI: the result streams up and renders as Markdown.

The resume-improvement flow has the same shape. The router picks the CV Assistant instead, and the bundled call comes back with gaps and suggestions rather than a ranking.

## Tech Stack

YAHR is written in Python and needs version 3.14 or newer. The command-line front end uses Typer, which turns the command functions into the `yahr` program, and Rich, which draws the status spinner, the job cards, and the Markdown replies in the terminal. Hatchling builds the package, so `pip install -e .` puts `yahr` on the path.

The two protocols each come from a reference SDK. A2A runs on `a2a-sdk`, with its `http-server` extra: the orchestrator talks to agents through the SDK's client, and each agent is an ASGI app that uvicorn serves over HTTP. MCP comes from the `mcp` package: the job-provider servers are built on its FastMCP helper, and the Job Searcher reaches them with the same package's client over streamable HTTP.

Every LLM call goes through OpenRouter, which exposes an OpenAI-compatible API, so YAHR uses the official `openai` client with its base URL pointed at OpenRouter. `httpx` is the async HTTP client under the A2A traffic. `markitdown` does the PDF text extraction for `convert`, pinned to `0.0.2` because the 0.1 line needs onnxruntime and there is still no Python 3.14 wheel for it. The job listings come from Adzuna's public API, which sits behind the Adzuna MCP server.

The Python is formatted and linted with ruff, and everything else (these docs included) with Prettier. A Husky pre-commit hook runs the formatters, and commitlint holds commit messages to the conventional-commits format.

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
async def _run(goal: Goal, fetch: Fetch = mock_jobs, refiner: Refiner = refine):
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

The agent cards import these names and the `serve()` functions bind these addresses, while the orchestrator's `discover()` walks `AGENT_URLS` fetching each card. Throughout, the code leans on plain dataclasses (`Job`, `Goal`, `AgentAddress`), type hints, and `asyncio`, and every core or logic module ends with an assert-based `__main__` self-check (see Testing).

## Testing

## Deployment

## Conclusion
