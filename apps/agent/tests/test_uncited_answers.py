"""An answer that cites nothing must not score as perfectly grounded.

`verified / total` is undefined at total = 0, so the value there is a convention.
It was 1.0, which made the metric reward vagueness: an answer naming no `file:line`
cannot cite anything false, so it collected a perfect score while delivering nothing
verifiable, and an agent that stopped citing would have posted 1.000 across a suite.

This is not hypothetical. Across six recorded B4 runs the branch fired twice —
both times in the arm with the citation fix, which reduced citation counts — and
each time collected a free 1.000. Recomputing those runs under this convention
flips the measured sign of that fix, which is why nothing about it was reported as
a score improvement. See `results/b4-citation-fix-experiment.md`.

**Mutation-verified, 3 reverts, all red** (exit code, not stdout substrings):

    # 1 — restore `score=1.0` in verify()'s no-citation branch
    #     → test_an_answer_with_no_citations_scores_zero
    #       test_the_exploit_is_closed_across_a_whole_suite
    # 2 — drop the _append_uncited_note branch in enforce_groundedness, leaving
    #     _append_guardrail_note for both cases
    #     → test_the_two_zero_score_failures_get_different_footnotes
    # 3 — delete "answers_without_citations" from _aggregate_metrics
    #     → test_the_aggregate_reports_the_no_citation_count
    #
    # uv run pytest apps/agent/tests/test_uncited_answers.py -q; echo "exit=$?"
"""

import pytest
from dcode_agent.groundedness import (
    CitationCheck,
    GroundednessResult,
    enforce_groundedness,
    verify,
)

THRESHOLD = 0.95


async def test_an_answer_with_no_citations_scores_zero() -> None:
    """No database is needed: extraction finds nothing, so nothing is looked up."""
    result = await verify("The request flows through the session and is then sent.", "x", None)

    assert result.citations == []
    assert result.score == 0.0, (
        "an answer citing nothing delivered nothing verifiable; scoring it 1.0 made "
        "the metric reward vagueness"
    )


async def test_a_cited_answer_is_still_scored_as_a_fraction() -> None:
    """The convention change must not touch the normal path.

    With no database every extracted citation fails, so this pins that citations are
    still found and still scored — a change that broke extraction would otherwise
    look identical to the no-citation case above.
    """
    result = await verify("See `src/requests/api.py:62` for the entry point.", "x", None)

    assert len(result.citations) == 1
    assert result.score == 0.0
    assert result.citations[0].verified is False


def test_the_two_zero_score_failures_get_different_footnotes() -> None:
    """0.0 alone cannot separate "cited nothing" from "cited things that all failed".

    Honesty_Constraints §4 forbids collapsing *never checked* into *checked and
    failed* for the marks on individual references. The same distinction has to
    survive here, and the footnote is where it does.
    """
    uncited = enforce_groundedness(
        "A prose answer with no code references.",
        GroundednessResult(citations=[], score=0.0),
        threshold=THRESHOLD,
    )
    all_failed = enforce_groundedness(
        "See `src/requests/api.py:62`.",
        GroundednessResult(
            citations=[
                CitationCheck(
                    symbol="src/requests/api.py",
                    file_path="src/requests/api.py",
                    line=62,
                    verified=False,
                )
            ],
            score=0.0,
        ),
        threshold=THRESHOLD,
    )

    assert uncited.score == all_failed.score == 0.0, "the scores are deliberately equal"
    assert "cites no indexed code" in uncited.answer
    assert "unverified reference" not in uncited.answer, (
        "nothing was stripped from this answer, so the note may not imply it was"
    )
    assert "unverified reference" in all_failed.answer
    assert "cites no indexed code" not in all_failed.answer


def test_the_aggregate_reports_the_no_citation_count() -> None:
    """The count is the mitigation for 0.0 being ambiguous, so it is not optional.

    Lives here rather than in the eval tests because it is the other half of this
    convention: without it, a baseline posting a low groundedness for the honest
    reason and one posting it for the useless reason read identically.
    """
    from dcode_eval.run import _aggregate_metrics

    rows = [
        {
            "citations": ["`a.py:1`"],
            "groundedness": 1.0,
            "recall_at_k": 0.0,
            "mrr": 0.0,
            "ndcg_at_k": 0.0,
        },
        {"citations": [], "groundedness": 0.0, "recall_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0},
        {"citations": [], "groundedness": 0.0, "recall_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0},
    ]
    metrics = _aggregate_metrics(rows, "B4", 5)

    assert metrics["answers_without_citations"] == 2
    assert metrics["groundedness"] == pytest.approx(1 / 3)
    # And the empty-suite shape carries the key too, so a consumer never has to
    # distinguish "no such field" from "none of them".
    assert _aggregate_metrics([], "B4", 5)["answers_without_citations"] == 0


def test_the_exploit_is_closed_across_a_whole_suite() -> None:
    """The case the convention exists for: an agent that simply stops citing.

    Under the old value this suite averaged 1.000 — a perfect grounding score for a
    system that grounded nothing.
    """
    from statistics import mean

    from dcode_eval.run import _aggregate_metrics

    rows = [
        {"citations": [], "groundedness": 0.0, "recall_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0}
        for _ in range(16)
    ]
    metrics = _aggregate_metrics(rows, "B4", 5)

    assert metrics["groundedness"] == 0.0
    assert metrics["answers_without_citations"] == 16
    assert mean(row["groundedness"] for row in rows) == 0.0
