"""Formula and tokenizer tests for the shared Okapi BM25 implementation."""

from math import isclose, log

import pytest
from dcode_shared.bm25 import (
    BM25_B,
    BM25_IMPLEMENTATION,
    BM25_K1,
    BM25_TOKENIZER,
    BM25Index,
    bm25_run_config,
    code_document_text,
    tokenize_code,
)


def test_code_tokenizer_keeps_identifiers_and_splits_code_conventions() -> None:
    tokens = tokenize_code("HTTPBasicAuth _basic_auth_str src/requests/auth.py")

    assert {"httpbasicauth", "http", "basic", "auth"}.issubset(tokens)
    assert {"basicauthstr", "str", "src", "requests", "py"}.issubset(tokens)


def test_bm25_uses_corpus_document_frequency_for_idf() -> None:
    index = BM25Index(["common rare", "common", "common"], b=0.0)

    rare_score = index.scores("rare")[0]
    common_score = index.scores("common")[0]

    assert rare_score > common_score


def test_bm25_term_frequency_saturates() -> None:
    index = BM25Index(["term", "term term", "term term term"], b=0.0)
    one, two, three = index.scores("term")

    assert one < two < three
    assert two - one > three - two


def test_bm25_normalizes_longer_documents() -> None:
    index = BM25Index(["needle", "needle filler filler filler filler"])
    short, long = index.scores("needle")

    assert short > long


def test_bm25_matches_the_declared_positive_idf_formula() -> None:
    index = BM25Index(["needle", "other"], k1=BM25_K1, b=0.0)
    expected_idf = log(1 + (2 - 1 + 0.5) / (1 + 0.5))

    assert isclose(index.scores("needle")[0], expected_idf)
    assert index.scores("needle")[1] == 0.0


def test_bm25_deduplicates_repeated_query_terms() -> None:
    index = BM25Index(["needle", "other"])

    assert index.scores("needle needle") == index.scores("needle")


def test_bm25_handles_an_empty_corpus() -> None:
    index = BM25Index([])

    assert index.document_count == 0
    assert index.average_document_length == 0.0
    assert index.scores("anything") == []


@pytest.mark.parametrize(
    ("k1", "b", "message"),
    [
        (0.0, BM25_B, "k1"),
        (BM25_K1, -0.1, "b"),
        (BM25_K1, 1.1, "b"),
    ],
)
def test_bm25_rejects_invalid_parameters(k1: float, b: float, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        BM25Index(["document"], k1=k1, b=b)


def test_bm25_run_config_and_document_definition_are_explicit() -> None:
    config = bm25_run_config()
    document = code_document_text(
        symbol_name="HTTPBasicAuth",
        file_path="src/requests/auth.py",
        signature="class HTTPBasicAuth(AuthBase)",
        content="class HTTPBasicAuth(AuthBase): pass",
    )

    assert config["implementation"] == BM25_IMPLEMENTATION
    assert config["tokenizer"] == BM25_TOKENIZER
    assert config["k1"] == BM25_K1
    assert config["b"] == BM25_B
    assert config["document_fields"] == ["symbol_name", "file_path", "signature", "content"]
    assert document.splitlines()[0] == "HTTPBasicAuth"
