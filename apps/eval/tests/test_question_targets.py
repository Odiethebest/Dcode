"""Ground-truth target resolution tests."""

from types import SimpleNamespace

import pytest
from dcode_eval.questions.models import GroundTruthTarget
from dcode_eval.questions.resolve import _select_target_chunk


def test_select_target_chunk_matches_stable_file_symbol_line_anchor() -> None:
    candidates = [
        SimpleNamespace(
            id="11111111-1111-1111-1111-111111111111",
            file_path="src/requests/sessions.py",
            symbol_name="Session",
            start_line=395,
            end_line=905,
        ),
        SimpleNamespace(
            id="22222222-2222-2222-2222-222222222222",
            file_path="src/requests/sessions.py",
            symbol_name="send",
            start_line=752,
            end_line=829,
        ),
    ]

    chunk_id = _select_target_chunk(
        "q-send",
        GroundTruthTarget(
            file_path="src/requests/sessions.py",
            symbol_name="send",
            start_line=752,
        ),
        candidates,
    )

    assert chunk_id == "22222222-2222-2222-2222-222222222222"


def test_select_target_chunk_rejects_ambiguous_target() -> None:
    candidates = [
        SimpleNamespace(
            id="11111111-1111-1111-1111-111111111111",
            file_path="src/requests/sessions.py",
            symbol_name="send",
            start_line=132,
            end_line=132,
        ),
        SimpleNamespace(
            id="22222222-2222-2222-2222-222222222222",
            file_path="src/requests/sessions.py",
            symbol_name="send",
            start_line=752,
            end_line=829,
        ),
    ]

    with pytest.raises(ValueError, match="ambiguous"):
        _select_target_chunk(
            "q-send",
            GroundTruthTarget(file_path="src/requests/sessions.py", symbol_name="send"),
            candidates,
        )
