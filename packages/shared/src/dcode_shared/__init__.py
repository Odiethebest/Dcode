"""Dcode shared package — single source of truth for schemas, DB models, SSE events, and cache keys.

Cross-service consumers MUST import schemas / event types from here rather than
redefining them. The current contracts are documented in
``docs/en/Technical_Design.md``.
"""

__version__ = "0.0.0"
