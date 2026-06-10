"""Dcode shared package — single source of truth for schemas, DB models, SSE events, and cache keys.

Cross-service consumers MUST import schemas / event types from here rather than
redefining. See DESIGN.md §3 (data model) and §4 (interface contracts).
"""

__version__ = "0.0.0"
