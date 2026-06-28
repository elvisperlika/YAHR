"""Adzuna job-board provider, exposed as an MCP server.

Split by context: extract.py (natural language → Adzuna params), client.py
(Adzuna HTTP + response parsing), server.py (the FastMCP `search` tool). The
public entry is `serve`.
"""

from yahr.mcp.adzuna.server import serve

__all__ = ["serve"]
