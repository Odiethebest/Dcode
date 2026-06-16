"""Question-set tests for the eval harness."""

from pathlib import Path

from dcode_eval.questions import load_questions


def test_requests_question_set_shape_and_size() -> None:
    path = Path("apps/eval/src/dcode_eval/questions/data/questions.jsonl")
    questions = load_questions(path)

    assert len(questions) == 16
    assert len({question.id for question in questions}) == 16
    assert all(question.source == "manual" for question in questions)
    assert all(question.gt_chunk_ids for question in questions)
    assert all(question.gt_files for question in questions)


def test_requests_question_set_taxonomy_balance() -> None:
    path = Path("apps/eval/src/dcode_eval/questions/data/questions.jsonl")
    questions = load_questions(path)

    counts = {"L1": 0, "L2": 0, "L3": 0}
    for question in questions:
        counts[question.taxonomy] += 1

    assert counts == {"L1": 5, "L2": 8, "L3": 3}
