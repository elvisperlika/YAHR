"""The job source, reached over MCP — the only provider the search loop knows.

The Job Searcher is agnostic to *which* job board it talks to: it connects to
whatever MCP server `jobs_mcp_url()` points at and calls that server's generic
`search(query)` tool. Adzuna, the mock, or any future source is just a different
MCP server URL (see yahr/mcp/), so nothing here is provider-specific.
"""

import json
from typing import Any, cast

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from yahr.agents.models.job import Job


class MCPProvider:
    """A job source reached over MCP via its `search` tool."""

    def __init__(self, url: str) -> None:
        """Bind the MCP server endpoint.

        Args:
            url: The provider MCP server's streamable-http URL (e.g.
                ``http://127.0.0.1:8005/mcp``).
        """
        self._url = url

    async def search(self, query: str) -> list[Job]:
        """Call the provider's `search` tool and map its result into Jobs.

        Args:
            query: The job query to search for.

        Returns:
            The jobs the provider returned (malformed entries skipped).
        """
        # ponytail: opens a fresh MCP session per call (the loop calls up to
        # 3×/task); fine at this scale — hold a persistent session if latency shows.
        async with streamable_http_client(self._url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search", {"query": query})
                return _to_jobs(result)


def _text(result: CallToolResult) -> str:
    """The first text content block of a tool result, or "" if there is none.

    Args:
        result: The CallToolResult to read.
    """
    return next((c.text for c in result.content if isinstance(c, TextContent)), "")


def _to_jobs(result: CallToolResult) -> list[Job]:
    """Map a `search` tool result into Jobs, skipping malformed entries.

    Reads the structured ``{"jobs": [...]}`` payload, falling back to the tool's
    text content (always JSON for our servers) when no structured content is set.

    Args:
        result: The CallToolResult from the provider's `search` tool.

    Returns:
        The parsed jobs.

    Raises:
        RuntimeError: If the tool reported an error (e.g. missing credentials).
    """
    if result.isError:
        raise RuntimeError(f"job provider error: {_text(result) or 'unknown error'}")
    payload: dict[str, Any] = result.structuredContent or {}
    if not payload:
        text = _text(result)
        payload = json.loads(text) if text else {}
    jobs: list[Job] = []
    for raw in payload.get("jobs", []):
        if not isinstance(raw, dict):
            continue  # tolerate a foreign server putting junk in the list
        entry = cast("dict[str, Any]", raw)
        job_id, title = entry.get("id"), entry.get("title")
        if not (job_id and title):
            continue  # need an id to dedupe and a title to show
        jobs.append(
            Job(
                id=str(job_id),
                title=str(title),
                company=str(entry.get("company", "")),
                location=str(entry.get("location", "")),
                description=str(entry.get("description", "")),
                url=str(entry.get("url", "")),
                salary=str(entry.get("salary", "")),
            )
        )
    return jobs


if __name__ == "__main__":
    # ponytail: check the tool-result -> Job mapping (the trust boundary), both
    # the structured and the text-fallback path, plus the error path. The live
    # MCP transport is left to a running server.
    good: dict[str, Any] = {
        "jobs": [
            {
                "id": 1,  # non-string id from a foreign server -> coerced
                "title": "Dev",
                "company": "Acme",
                "location": "Milano",
                "salary": "€30,000",
            },
            {"id": None, "title": "No id"},  # skipped
            {"title": "Missing id"},  # skipped
            "not a dict",  # skipped
        ]
    }
    text = TextContent(type="text", text=json.dumps(good))

    structured = _to_jobs(CallToolResult(content=[text], structuredContent=good))
    assert [j.id for j in structured] == ["1"], structured
    assert structured[0].company == "Acme" and structured[0].salary == "€30,000"

    # No structured content -> parse the text part instead.
    fallback = _to_jobs(CallToolResult(content=[text]))
    assert [j.id for j in fallback] == ["1"], fallback

    # Error result surfaces, never silently empty.
    err = CallToolResult(
        content=[TextContent(type="text", text="creds missing")], isError=True
    )
    try:
        _to_jobs(err)
        raise AssertionError("error result must raise")
    except RuntimeError as exc:
        assert "creds missing" in str(exc), exc

    print("providers (mcp client) self-check ok")
