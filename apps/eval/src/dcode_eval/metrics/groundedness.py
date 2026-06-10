"""Groundedness metric — DESIGN.md §2.4.4 (Faithfulness) + D-2.3.1.

The agent service already runs programmatic groundedness as a hard guardrail
(see apps/agent/src/dcode_agent/groundedness.py). The eval harness consumes
the same metric — either by reading the score the agent emits, or by
re-running the verifier offline.

We expose a `GroundednessChecker` ABC so the harness can swap between
"trust the agent's emitted score" and "re-verify against the live index"
without code churn.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GroundednessRow:
    citations_total: int
    citations_verified: int
    score: float  # = verified / total ∈ [0, 1]


class GroundednessChecker(ABC):
    """Abstract verifier — implementations live in M3."""

    @abstractmethod
    async def check(self, answer: str, repo_id: str) -> GroundednessRow:
        """Verify every citation in `answer` against the live index."""
