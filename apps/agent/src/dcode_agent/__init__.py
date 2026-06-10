"""Dcode Agent Orchestrator — implements DESIGN.md §2.3.

A standalone FastAPI service that the API gateway proxies query traffic to.
Exposes `/internal/query` (SSE) + `/healthz` + `/internal/tools` (manifest).
"""

__version__ = "0.0.0"
