"""Job-provider MCP servers, one subpackage each.

Each subpackage (adzuna/, mock/) is a standalone MCP server exposing one generic
tool — ``search(query) -> {"jobs": [...]}`` — over streamable-http, split into
decoupled context files. The Job Searcher agent reaches them as an MCP client
(see agents/job_searcher/providers.py), so all provider-specific work lives
behind the MCP boundary and never leaks into the agent.
"""
