## Testing

Testing follows from the same split that shapes the code: because every agent keeps a protocol-free core apart from its A2A executor, the logic can be exercised without a server, a port, or a network. Each core and logic module ends with an assert-based `__main__` self-check that does exactly that. The check imports nothing from `a2a`, makes no HTTP call, and reaches no LLM, so running the module runs its tests offline and in a fraction of a second. There is no test framework and no separate test tree; the checks live at the bottom of the module they guard, next to the code they describe.

The self-checks target the pure logic, the parts that must be right regardless of what the model or the job board returns. `refine.py` checks the deterministic `_broaden` fallback (dropping a seniority qualifier, then the trailing token, then converging on a single-token query) and the `_clean` validation that decides when an LLM reply is unusable and the fallback takes over. `roster.py` asserts the invariants that would silently break a run if they drifted: every server binds a distinct port, 8004 stays reserved, and the orchestrator's discovery list holds exactly the three A2A agents and neither MCP server. `config.py` checks that a pasted OpenRouter URL ending in `/chat/completions` is trimmed back to the base the SDK expects, and that the `.env` loader skips comments and malformed lines, strips quotes, and never overrides a value already in the environment. The Job Searcher's core checks its three stop conditions and the id-based dedupe, and the Adzuna modules check their query mapping and description trimming.

Running one check is `python -m yahr.<module>`, which prints a single `... self-check ok` line on success or raises an `AssertionError` at the first broken invariant. The whole suite is the same command over each module:

```sh
for m in agents.roster config \
         agents.job_searcher.refine agents.job_searcher.core \
         agents.ranker.core agents.cv_assistant.core \
         mcp.mock.jobs mcp.adzuna.extract mcp.adzuna.enrich mcp.adzuna.client \
         agents.job_searcher.providers agents.orchestrator; do
  python -m "yahr.$m" || break
done
```

The boundary is deliberate. The self-checks cover the deterministic logic, not the best-effort paths that depend on an outside service: an actual OpenRouter completion, a live Adzuna page, or a running A2A agent answering over HTTP. Those are the seams the design already treats as fallible, where a failed model call drops to a heuristic and an unreachable page keeps its truncated text, so they are validated by their fallbacks rather than by asserting on a network round-trip. Testing the agent-to-agent and MCP flows end to end would need fixtures that start servers and mock the model, which is where a `pytest` suite would earn its place; the current checks stop where a server or a network would have to start.
