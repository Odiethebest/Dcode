"""Citation verification — implements DESIGN.md §2.3.4 and D-2.3.1.

For every code reference in a draft answer, this module queries the live
index to confirm existence. Unverified references are flagged or stripped
before the answer is returned.

**D-2.3.1 — Groundedness is a HARD GUARDRAIL.** It must not be disable-able
in production: the same routine produces the ≥95% groundedness number that
NFR-4 and PLAN.md §3.1 measure against.
"""

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

# Regex patterns for citation extraction.
# Pattern 1: bare or backticked `path/to/file.py:42`
FILE_LINE_PATTERN = re.compile(r"`?([\w./\-]+\.py):(\d+)`?")
# Pattern 2: backticked qualified-name with at least one dot, e.g. `flask.app.Flask.run`
SYMBOL_PATTERN = re.compile(r"`([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)`")


@dataclass
class CitationCheck:
    symbol: str
    file_path: str
    line: int
    verified: bool


@dataclass
class GroundednessResult:
    citations: list[CitationCheck]
    score: float  # fraction verified — 1.0 means every citation found in index


def extract_citations(answer: str) -> list[tuple[str, str, int]]:
    """Pull (symbol, file_path, line) tuples out of an answer string.

    For file:line references, `symbol` is set to the file path itself.
    For qualified-name references, `file_path` and `line` are zeroed and
    resolved later via an index lookup.
    """
    out: list[tuple[str, str, int]] = []
    for match in FILE_LINE_PATTERN.finditer(answer):
        file_path, line_str = match.group(1), match.group(2)
        out.append((file_path, file_path, int(line_str)))
    for match in SYMBOL_PATTERN.finditer(answer):
        out.append((match.group(1), "", 0))
    return out


async def verify(answer: str, repo_id: str, db: AsyncSession | None) -> GroundednessResult:
    """Verify every citation in `answer` against indexed chunks / symbols.

    TODO(M2): real SELECT against `chunks (repo_id, file_path)` and
    `symbols (repo_id, qualified_name)` per DESIGN.md §3.2. Until then we
    return verified=False for every extracted citation so the score is 0
    (rather than falsely 1.0).
    """
    extracted = extract_citations(answer)
    if not extracted:
        return GroundednessResult(citations=[], score=1.0)

    checks = [
        CitationCheck(symbol=sym, file_path=path, line=line, verified=False)
        for sym, path, line in extracted
    ]
    verified_count = sum(1 for c in checks if c.verified)
    score = verified_count / len(checks) if checks else 1.0
    return GroundednessResult(citations=checks, score=score)
