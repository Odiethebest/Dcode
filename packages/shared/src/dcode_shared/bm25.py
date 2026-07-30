"""Auditable Okapi BM25 scoring for code-search corpora.

The scorer deliberately owns no database or cache concerns.  Callers provide the
complete corpus for one repository, and this module provides the code-aware
tokenization and corpus-wide statistics that make the sparse ranker BM25 rather
than a collection of substring bonuses.
"""

import re
from collections import Counter
from collections.abc import Sequence
from math import log

BM25_IMPLEMENTATION = "okapi_bm25_v1"
BM25_TOKENIZER = "dcode_source_code_v1"
BM25_K1 = 1.2
BM25_B = 0.75
BM25_DOCUMENT_FIELDS = ("symbol_name", "file_path", "signature", "content")

_RAW_TOKEN_RE = re.compile(r"[^\W_]+(?:_[^\W_]+)*", re.UNICODE)
_CAMEL_PART_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|\Z)|[A-Z]?[a-z]+|[0-9]+|[A-Z]+")


def tokenize_code(text: str) -> list[str]:
    """Tokenize prose, paths, snake_case, and camelCase consistently.

    Each identifier contributes its compact case-folded form as well as its
    casing/underscore components.  Keeping both means an exact query for
    ``HTTPBasicAuth`` and a conceptual query for ``basic auth`` can match the
    same document without adding field-specific ranking bonuses.
    """

    tokens: list[str] = []
    for raw_token in _RAW_TOKEN_RE.findall(text):
        compact = raw_token.replace("_", "").casefold()
        token_variants = [compact]
        for segment in raw_token.split("_"):
            parts = _CAMEL_PART_RE.findall(segment)
            if not parts:
                parts = [segment]
            token_variants.extend(part.casefold() for part in parts)

        # Avoid counting the compact form twice for ordinary one-part words.
        tokens.extend(dict.fromkeys(token for token in token_variants if token))
    return tokens


def code_document_text(
    *,
    symbol_name: str,
    file_path: str,
    signature: str | None,
    content: str,
) -> str:
    """Build the single, unweighted text document used by the BM25 baseline."""

    return "\n".join((symbol_name, file_path, signature or "", content))


class BM25Index:
    """An immutable in-memory Okapi BM25 index over one complete corpus."""

    def __init__(
        self,
        documents: Sequence[str],
        *,
        k1: float = BM25_K1,
        b: float = BM25_B,
    ) -> None:
        if k1 <= 0:
            raise ValueError("BM25 k1 must be greater than zero")
        if not 0 <= b <= 1:
            raise ValueError("BM25 b must be between zero and one")

        term_frequencies = tuple(Counter(tokenize_code(document)) for document in documents)
        document_frequency: Counter[str] = Counter()
        for frequencies in term_frequencies:
            document_frequency.update(frequencies.keys())

        self.k1 = k1
        self.b = b
        self._term_frequencies = term_frequencies
        self._document_frequency = document_frequency
        self._document_lengths = tuple(
            sum(frequencies.values()) for frequencies in term_frequencies
        )
        self.document_count = len(documents)
        self.average_document_length = (
            sum(self._document_lengths) / self.document_count if self.document_count else 0.0
        )

    def scores(self, query: str) -> list[float]:
        """Return one BM25 score per document, preserving corpus order."""

        if not self.document_count:
            return []

        # Classic BM25 commonly omits query-term-frequency saturation for short
        # search queries.  Deduplicating here makes that choice explicit.
        query_terms = tuple(dict.fromkeys(tokenize_code(query)))
        scores = [0.0] * self.document_count
        for term in query_terms:
            document_frequency = self._document_frequency.get(term, 0)
            if document_frequency == 0:
                continue
            inverse_document_frequency = log(
                1 + (self.document_count - document_frequency + 0.5) / (document_frequency + 0.5)
            )

            for index, frequencies in enumerate(self._term_frequencies):
                term_frequency = frequencies.get(term, 0)
                if term_frequency == 0:
                    continue
                normalized_length = (
                    self._document_lengths[index] / self.average_document_length
                    if self.average_document_length
                    else 0.0
                )
                denominator = term_frequency + self.k1 * (1 - self.b + self.b * normalized_length)
                scores[index] += inverse_document_frequency * (
                    term_frequency * (self.k1 + 1) / denominator
                )
        return scores


def bm25_run_config() -> dict[str, object]:
    """Return stable methodology metadata for evaluation run artifacts."""

    return {
        "implementation": BM25_IMPLEMENTATION,
        "idf": "ln(1 + (N - df + 0.5) / (df + 0.5))",
        "k1": BM25_K1,
        "b": BM25_B,
        "tokenizer": BM25_TOKENIZER,
        "document_fields": list(BM25_DOCUMENT_FIELDS),
        "field_weighting": "none",
        "query_term_frequency": "deduplicated",
    }
