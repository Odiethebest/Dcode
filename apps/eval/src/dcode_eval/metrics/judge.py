"""Answer-quality judge contract and current stub implementation.

The intended real judge produces:
  - 4-axis rubric scores (correctness, completeness, faithfulness, actionability)
  - pairwise win-rates between competing answers

No real judge client is wired today. The stub keeps the contract executable,
while reports mark pairwise win-rate as unmeasured rather than treating ties or
zero rubric scores as a result.
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
    """Abstract answer-quality judge client."""

    @abstractmethod
    async def score(self, question: str, answer: str, gt: str | None = None) -> JudgeScore:
        """4-axis rubric score in [0, 1] per axis."""

    @abstractmethod
    async def pairwise(self, question: str, answer_a: str, answer_b: str) -> PairwiseVerdict:
        """Return 'a', 'b', or 'tie' — used for win-rate calculation."""


class StubJudge(Judge):
    """Non-evaluating placeholder; its outputs must not be reported as measured."""

    async def score(self, question: str, answer: str, gt: str | None = None) -> JudgeScore:
        return JudgeScore(0.0, 0.0, 0.0, 0.0)

    async def pairwise(self, question: str, answer_a: str, answer_b: str) -> PairwiseVerdict:
        return "tie"
