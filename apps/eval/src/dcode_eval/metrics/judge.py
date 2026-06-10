"""LLM-as-Judge — DESIGN.md §2.4.4 (Answer Quality) + OD-4 placeholder.

Per PLAN.md §3.1 the judge produces:
  - 4-axis rubric scores (correctness, completeness, faithfulness, actionability)
  - pairwise win-rates between competing answers

The judge model itself is Open Decision OD-4 (PLAN.md §9). We define the
client as an ABC so M3 can plug in the OD-4-resolved model without touching
the harness internals.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

PairwiseVerdict = Literal["a", "b", "tie"]


@dataclass
class JudgeScore:
    correctness: float
    completeness: float
    faithfulness: float
    actionability: float


class Judge(ABC):
    """Abstract OD-4 LLM-as-Judge client."""

    @abstractmethod
    async def score(self, question: str, answer: str, gt: str | None = None) -> JudgeScore:
        """4-axis rubric score in [0, 1] per axis."""

    @abstractmethod
    async def pairwise(self, question: str, answer_a: str, answer_b: str) -> PairwiseVerdict:
        """Return 'a', 'b', or 'tie' — used for win-rate calculation."""


class StubJudge(Judge):
    """Skeleton placeholder. Replaced at M3 once OD-4 is resolved."""

    async def score(self, question: str, answer: str, gt: str | None = None) -> JudgeScore:
        return JudgeScore(0.0, 0.0, 0.0, 0.0)

    async def pairwise(self, question: str, answer_a: str, answer_b: str) -> PairwiseVerdict:
        return "tie"
