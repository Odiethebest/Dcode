"""Versioned validation cases for internal retrieval APIs."""

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "requests_query_cases.json"
_LIVE_REPO_ID = os.getenv("DCODE_LIVE_REPO_ID")
_LIVE_API_BASE_URL = os.getenv("DCODE_LIVE_API_BASE_URL", "http://localhost:8000")
_ALLOWED_ENDPOINTS = {
    "search",
    "find_definition",
    "find_references",
    "get_dependencies",
    "get_file_outline",
}


def _load_query_cases() -> list[dict[str, Any]]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


_QUERY_CASES = _load_query_cases()


def test_requests_query_cases_cover_internal_validation_surface() -> None:
    assert len(_QUERY_CASES) == 5
    assert len({case["id"] for case in _QUERY_CASES}) == 5

    for case in _QUERY_CASES:
        assert case["endpoint"] in _ALLOWED_ENDPOINTS
        assert isinstance(case["params"], dict)
        assert isinstance(case["expect"], dict)
        assert case["expect"]


@pytest.mark.skipif(
    _LIVE_REPO_ID is None,
    reason="set DCODE_LIVE_REPO_ID to run live internal retrieval validation",
)
@pytest.mark.parametrize("case", _QUERY_CASES, ids=[case["id"] for case in _QUERY_CASES])
def test_live_internal_api_requests_cases(case: dict[str, Any]) -> None:
    query = urlencode({"repo_id": _LIVE_REPO_ID, **case["params"]})
    url = f"{_LIVE_API_BASE_URL}/internal/{case['endpoint']}?{query}"

    with urlopen(url) as response:
        assert response.status == 200
        body = json.loads(response.read().decode("utf-8"))

    assert isinstance(body, list)
    assert body
    _assert_case_expectations(case["expect"], body)


def _assert_case_expectations(expect: dict[str, Any], body: list[dict[str, Any]]) -> None:
    files = [item["file_path"] for item in body]
    symbols = [_item_symbol(item) for item in body]

    top_file = expect.get("top_file")
    if top_file is not None:
        assert files[0] == top_file

    top_symbol = expect.get("top_symbol")
    if top_symbol is not None:
        assert symbols[0] == top_symbol

    must_include_files = expect.get("must_include_files", [])
    if must_include_files:
        assert set(must_include_files).issubset(files)

    must_include_symbols = expect.get("must_include_symbols", [])
    if must_include_symbols:
        assert set(must_include_symbols).issubset(symbols)

    ordered_symbols_prefix = expect.get("ordered_symbols_prefix", [])
    if ordered_symbols_prefix:
        assert symbols[: len(ordered_symbols_prefix)] == ordered_symbols_prefix


def _item_symbol(item: dict[str, Any]) -> str:
    symbol = item.get("symbol")
    if isinstance(symbol, str):
        return symbol
    symbol_name = item.get("symbol_name")
    if isinstance(symbol_name, str):
        return symbol_name
    raise AssertionError(f"response item missing symbol field: {item}")
