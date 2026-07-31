"""Groundedness metric contract for evaluation.

The agent service already runs programmatic groundedness as a hard guardrail
(see apps/agent/src/dcode_agent/groundedness.py). The eval harness consumes
the same metric — either by reading the score the agent emits, or by
re-running the verifier offline.

The `GroundednessChecker` ABC leaves room for an offline live-index verifier;
the current harness consumes the score and citations emitted by each baseline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GroundednessRow:
    citations_total: int
    citations_verified: int
    score: float  # verified fraction; zero citations use the project-wide 0.0 convention


class GroundednessChecker(ABC):
    """Optional offline verifier interface; no concrete live client is wired yet."""

    @abstractmethod
    async def check(self, answer: str, repo_id: str) -> GroundednessRow:
        """Verify every citation in `answer` against the live index."""
