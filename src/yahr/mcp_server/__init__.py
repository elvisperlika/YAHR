"""Job-provider MCP servers.

Each module here is a standalone MCP server exposing one generic tool —
``search(query) -> {"jobs": [...]}`` — over streamable-http. The Job Searcher
agent reaches them as an MCP client (see agents/job_searcher/providers.py), so
all provider-specific work (Adzuna's HTTP, credentials, LLM param extraction)
lives behind the MCP boundary and never leaks into the agent.
"""
