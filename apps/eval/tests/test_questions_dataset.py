"""Question-set tests for the eval harness."""

from pathlib import Path

from dcode_eval.questions import load_questions


def test_requests_question_set_shape_and_size() -> None:
    path = Path("apps/eval/src/dcode_eval/questions/data/questions.jsonl")
    questions = load_questions(path)

    assert len(questions) == 33
    assert len({question.id for question in questions}) == 33
    assert all(question.source in {"manual", "graph_reverse"} for question in questions)
    assert all(question.gt_files for question in questions)
    # Every question must be resolvable by at least one route: the original 16
    # carry recorded chunk ids, the graph_reverse batch carries stable anchors
    # only, because index-specific chunk uuids must not be hard-coded.
    assert all(question.gt_chunk_ids or question.gt_targets for question in questions)


def test_graph_reverse_questions_carry_stable_anchors_only() -> None:
    """The expansion batch must be resolvable against any re-index.

    `graph_reverse` records how these questions were built: reverse-constructed
    from the indexed call relationships and source of the current corpus. That
    provenance is deliberately visible in the artifact, because a suite derived
    from the system's own graph output cannot include a flow the graph misses,
    which biases B4 upward. Read alongside `docs/en/Final_Report.md`.
    """
    path = Path("apps/eval/src/dcode_eval/questions/data/questions.jsonl")
    expansion = [q for q in load_questions(path) if q.source == "graph_reverse"]

    assert len(expansion) == 17
    for question in expansion:
        assert question.gt_chunk_ids == []
        assert question.gt_targets
        assert all(target.symbol_name and target.start_line for target in question.gt_targets)
        # The batch exists to add genuinely cross-file evidence.
        assert len(set(question.gt_files)) >= 2


def test_requests_question_set_taxonomy_balance() -> None:
    path = Path("apps/eval/src/dcode_eval/questions/data/questions.jsonl")
    questions = load_questions(path)

    counts = {"L1": 0, "L2": 0, "L3": 0}
    for question in questions:
        counts[question.taxonomy] += 1

    assert counts == {"L1": 5, "L2": 16, "L3": 12}
