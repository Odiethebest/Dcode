"""Abstract contracts shared by evaluation baselines B0 through B4.

Every baseline exposes two contracts:
  - `retrieve(repo_id, query, k)` → ranked chunks (for Recall@k / MRR / nDCG)
  - `answer(repo_id, query)`      → full answer (for judge + groundedness)

The split lets us compute pure-retrieval deltas independently from
answer-quality deltas.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from dcode_shared.schemas import Chunk


@dataclass
class AnswerResult:
    answer: str
    citations: list[str] = field(default_factory=list)
    groundedness: float = 1.0


class Baseline(ABC):
    """Base class for B0..B4."""

    id: ClassVar[str] = ""
    description: ClassVar[str] = ""

    @abstractmethod
    async def retrieve(self, repo_id: str, query: str, k: int) -> list[Chunk]:
        """Retrieve top-k chunks for the query."""

    @abstractmethod
    async def answer(self, repo_id: str, query: str) -> AnswerResult:
        """Produce a full natural-language answer."""
