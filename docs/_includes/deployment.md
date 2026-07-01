## Deployment

YAHR deploys as a set of local processes on one machine. There is no cloud, no container, no orchestration platform. The candidate installs the package once and runs `yahr` from a terminal, and every part of the system is a process that starts and stops on that same host. This follows from the domain: one person looking for work on their own machine, so the deployment never has to deal with multi-tenancy, remote access, or shared state.

Installation is a single editable install. YAHR needs Python 3.14 or newer; from a virtual environment, `pip install -e .` builds the package with Hatchling and puts the `yahr` command on the path. Every process starts through that one command.

At runtime there are two layers of process. The A2A agents and the job-provider MCP servers are long-running servers, each started with `yahr serve <name>` and each binding its own TCP port on `127.0.0.1`:

| Server             | `serve` name   | Port |
| ------------------ | -------------- | ---- |
| Job Searcher (A2A) | `job-searcher` | 8002 |
| Ranker (A2A)       | `ranker`       | 8003 |
| CV Assistant (A2A) | `cv-assistant` | 8007 |
| Adzuna (MCP)       | `adzuna-mcp`   | 8005 |
| Mock jobs (MCP)    | `mock-mcp`     | 8006 |

They bind the loopback interface only, so nothing is reachable from outside the machine. The addresses come from the roster, the single source of truth described in the Code section, so the port a server binds and the port the orchestrator probes for it are the same value written once.

The two kinds of server run on different stacks. Each A2A agent is a Starlette ASGI app that uvicorn serves over HTTP, with its agent card at the well-known URI and its JSON-RPC endpoint at the root. Each MCP server is a FastMCP app served over streamable HTTP, mounted at `/mcp`. The candidate starts only the servers a run needs: a ranking run wants a job-provider server, the Job Searcher, and the Ranker, each in its own terminal, while an offline run swaps the Adzuna server for the mock and points `YAHR_JOBS_MCP_URL` at it.

The orchestrator is not a server. It runs in-process inside `yahr start`, so the CLI itself is the second layer: a short-lived process that reads the query and resume, routes to whichever agents are up, streams the result, and exits, or stays open as the REPL. Port 8004 is reserved for a standalone orchestrator that is planned but not yet built. Because `start` only routes to agents that are actually running and serving a card, an agent is part of a run exactly when its server is up. A new agent joins the same way: start its server, list it in the roster, and nothing else changes.

The deployment keeps almost no state, and what little it keeps is plain files. Each agent holds its A2A task state in an in-memory store, so those tasks vanish on restart and there is no database. What does survive is two files the orchestrator writes under `output/`: `jobs.md`, the jobs the Job Searcher last found, and `resume.md`, the converted profile that `convert` writes and `start` reads back. They persist on disk on purpose, so a later ranking or resume query can reuse the jobs and the resume without a fresh search or re-attaching the file; a restart picks them up rather than starting clean. Configuration is external, read at startup from the environment or a local `.env`: the OpenRouter key, base URL, and model for every reasoning step, the Adzuna credentials plus the optional `ADZUNA_COUNTRY` (defaults to `it`) for real listings, and `YAHR_JOBS_MCP_URL` to choose the job provider. The only things the deployment reaches off the machine are those two HTTPS services: OpenRouter for the model calls and Adzuna for the listings behind its MCP server. Everything else is loopback traffic between local processes.
