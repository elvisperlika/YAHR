"""Deterministic mock job provider, exposed as an MCP server.

Split by context: jobs.py (the canned, network-free data) and server.py (the
FastMCP `search` tool). `serve` runs it; `mock_jobs` is reused directly as the
search loop's offline default fetch.
"""

from yahr.mcp.mock.jobs import mock_jobs
from yahr.mcp.mock.server import serve

__all__ = ["mock_jobs", "serve"]
