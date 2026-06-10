"""SQLAlchemy 2.0 ORM layer for Dcode (DESIGN.md §3 Data Model)."""

from dcode_shared.db.models import (
    Base,
    Chunk,
    Edge,
    Repo,
    Symbol,
)
from dcode_shared.db.session import SessionLocal, engine

__all__ = ["Base", "Chunk", "Edge", "Repo", "Symbol", "SessionLocal", "engine"]
