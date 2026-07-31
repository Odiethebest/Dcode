"""Citation verification for Dcode's hard groundedness guardrail.

For every citation in a draft answer, :func:`verify` queries the live index to
confirm existence; :func:`enforce_groundedness` then redacts every unverified
citation before the answer is returned, so an unverified code location is never
presented to the user as evidence. In LLM synthesis mode, server-owned evidence
IDs and explicit ``file.py:line`` locations are citations; ordinary inline code
is formatting and is deliberately not treated as an implicit evidence claim.

The same routine produces the pre-redaction score compared with the 95% product
threshold. See ``docs/en/Honesty_Constraints.md`` for the scoring and redaction
contract.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from dcode_shared.db.models import Chunk, Symbol
from dcode_shared.symbols import candidate_filter, select_symbol_matches
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Regex patterns for citation extraction.
# Pattern 1: bare or backticked `path/to/file.py:42`
FILE_LINE_PATTERN = re.compile(r"`?([\w./\-]+\.py):(\d+)`?")
# Pattern 2: backticked qualified-name with at least one dot, e.g. `flask.app.Flask.run`
SYMBOL_PATTERN = re.compile(r"`([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)`")
# LLM synthesis uses server-owned evidence IDs. Ordinary inline code remains
# ordinary inline code and is not interpreted as a citation in that mode.
EVIDENCE_ID_PATTERN = re.compile(r"\[(C\d+)\]")


@dataclass
class EvidenceTarget:
    """One server-owned target offered to synthesis under a request-local ID."""

    display_token: str
    chunk_id: str = ""
    origins: tuple[str, ...] = ()


@dataclass
class CitationCheck:
    symbol: str
    file_path: str
    line: int
    verified: bool
    # The exact evidence ID emitted by the LLM, e.g. ``[C1]``. Empty for the
    # legacy citation protocol used by templates and historical eval artifacts.
    source_token: str = ""
    # Server-owned token rendered after verification, e.g. ``src/pkg/mod.py:42``.
    display_token: str = ""
    # Stable evidence identity used by evaluation. Empty only when the verified
    # symbol/location cannot be tied to an indexed chunk.
    chunk_id: str = ""
    # Request-local ID without brackets, e.g. ``C1``.
    evidence_id: str = ""
    # Tools that surfaced this evidence. Multiple origins are retained when the
    # same chunk appeared in both hybrid retrieval and graph expansion.
    origins: tuple[str, ...] = ()


@dataclass
class GroundednessResult:
    citations: list[CitationCheck]
    score: float  # verified fraction; 0.0 by convention when the draft cites nothing


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


def extract_evidence_ids(answer: str) -> list[str]:
    """Extract evidence IDs in occurrence order, including duplicates."""
    return [match.group(1) for match in EVIDENCE_ID_PATTERN.finditer(answer)]


async def verify(
    answer: str,
    repo_id: str,
    db: AsyncSession | None,
    *,
    evidence_catalog: Mapping[str, str | EvidenceTarget] | None = None,
) -> GroundednessResult:
    """Verify every citation in ``answer`` against indexed chunks / symbols.

    ``evidence_catalog is None`` selects the legacy protocol used by template
    synthesis and historical eval artifacts: backticked dotted names and
    file:line tokens are citations. Passing a catalog selects the LLM protocol:
    only server-owned ``[C#]`` IDs and explicit file:line tokens are citations,
    so ordinary code such as ``self.faiss.retrieve`` is not misclassified.
    """
    if evidence_catalog is not None:
        return await _verify_with_evidence_catalog(answer, repo_id, db, evidence_catalog)

    extracted = extract_citations(answer)
    if not extracted:
        return _uncited_result()

    parsed_repo_id = _parse_repo_id(repo_id)

    checks: list[CitationCheck] = []
    for sym, path, line in extracted:
        if db is None or parsed_repo_id is None:
            checks.append(CitationCheck(symbol=sym, file_path=path, line=line, verified=False))
            continue

        if path and line > 0:
            checks.append(await _verify_file_line(db, parsed_repo_id, sym, path, line))
            continue

        checks.append(await _verify_symbol(db, parsed_repo_id, sym))

    verified_count = sum(1 for c in checks if c.verified)
    score = verified_count / len(checks) if checks else 1.0
    return GroundednessResult(citations=checks, score=score)


async def _verify_with_evidence_catalog(
    answer: str,
    repo_id: str,
    db: AsyncSession | None,
    evidence_catalog: Mapping[str, str | EvidenceTarget],
) -> GroundednessResult:
    """Verify LLM evidence IDs plus explicit file:line references.

    File:line remains recognized as a defensive compatibility path: a model
    that ignores the ID instruction still cannot present an invented location
    as evidence. Dotted inline code is intentionally absent from this extractor.
    """
    references: list[tuple[int, str, Any]] = []
    references.extend(
        (match.start(), "evidence_id", match.group(1))
        for match in EVIDENCE_ID_PATTERN.finditer(answer)
    )
    references.extend(
        (
            match.start(),
            "file_line",
            (match.group(1), match.group(1), int(match.group(2))),
        )
        for match in FILE_LINE_PATTERN.finditer(answer)
    )
    references.sort(key=lambda item: item[0])
    if not references:
        return _uncited_result()

    parsed_repo_id = _parse_repo_id(repo_id)
    checks: list[CitationCheck] = []
    for _, reference_kind, payload in references:
        if reference_kind == "file_line":
            symbol, path, line = payload
            if db is None or parsed_repo_id is None:
                checks.append(
                    CitationCheck(symbol=symbol, file_path=path, line=line, verified=False)
                )
            else:
                checks.append(await _verify_file_line(db, parsed_repo_id, symbol, path, line))
            continue

        evidence_id = str(payload)
        source_token = f"[{evidence_id}]"
        catalog_entry = evidence_catalog.get(evidence_id)
        if catalog_entry is None:
            checks.append(
                CitationCheck(
                    symbol=source_token,
                    file_path="",
                    line=0,
                    verified=False,
                    source_token=source_token,
                )
            )
            continue
        target = (
            catalog_entry
            if isinstance(catalog_entry, EvidenceTarget)
            else EvidenceTarget(display_token=catalog_entry)
        )
        display_token = target.display_token
        check = await _verify_catalog_token(db, parsed_repo_id, display_token)
        checks.append(
            CitationCheck(
                symbol=check.symbol,
                file_path=check.file_path,
                line=check.line,
                verified=check.verified,
                source_token=source_token,
                display_token=display_token,
                chunk_id=target.chunk_id or check.chunk_id,
                evidence_id=evidence_id,
                origins=target.origins,
            )
        )

    verified_count = sum(1 for check in checks if check.verified)
    return GroundednessResult(citations=checks, score=verified_count / len(checks))


def _extract_file_line_citations(answer: str) -> list[tuple[str, str, int]]:
    return [
        (match.group(1), match.group(1), int(match.group(2)))
        for match in FILE_LINE_PATTERN.finditer(answer)
    ]


async def _verify_catalog_token(
    db: AsyncSession | None,
    repo_id: UUID | None,
    token: str,
) -> CitationCheck:
    file_line = FILE_LINE_PATTERN.fullmatch(token)
    if file_line is not None:
        path, line_text = file_line.group(1), file_line.group(2)
        line = int(line_text)
        if db is None or repo_id is None:
            return CitationCheck(symbol=path, file_path=path, line=line, verified=False)
        return await _verify_file_line(db, repo_id, path, path, line)

    qualified_symbol = SYMBOL_PATTERN.fullmatch(f"`{token}`")
    if qualified_symbol is not None:
        if db is None or repo_id is None:
            return CitationCheck(symbol=token, file_path="", line=0, verified=False)
        return await _verify_symbol(db, repo_id, token)

    return CitationCheck(symbol=token, file_path="", line=0, verified=False)


def _parse_repo_id(repo_id: str) -> UUID | None:
    try:
        return UUID(repo_id)
    except ValueError:
        return None


def _uncited_result() -> GroundednessResult:
    # An answer citing nothing scores ZERO, not one.
    #
    # `verified / total` is undefined at total = 0, so this is a convention and
    # not an implementation of a fact. It used to be 1.0, which made the metric
    # reward vagueness: an answer that names no `file:line` cannot cite anything
    # false, so it collected a perfect grounding score while delivering nothing
    # verifiable — and an agent that stopped citing altogether would have posted
    # 1.000 across a whole suite.
    #
    # Chosen at 0.0 rather than excluded-from-the-average because excluding has
    # its own exploit: an agent that cites nothing exactly where it is unsure
    # drops those questions from the denominator and raises the mean over the
    # rest. The empty/non-empty citations list plus the enforcement footnote
    # preserves the distinction between "nothing cited" and "everything failed".
    return GroundednessResult(citations=[], score=0.0)


async def _verify_file_line(
    db: AsyncSession,
    repo_id: UUID,
    symbol: str,
    file_path: str,
    line: int,
) -> CitationCheck:
    stmt = (
        select(Chunk)
        .where(Chunk.repo_id == repo_id)
        .where(Chunk.file_path == file_path)
        .where(Chunk.start_line <= line)
        .where(Chunk.end_line >= line)
        # Prefer the narrowest/nearest containing chunk deterministically. The
        # previous unordered LIMIT could map the same citation differently when
        # a class chunk and a nested method both contained the cited line.
        .order_by(Chunk.start_line.desc(), Chunk.end_line.asc(), Chunk.id)
        .limit(1)
    )
    row = await db.scalar(stmt)
    return CitationCheck(
        symbol=symbol,
        file_path=file_path,
        line=line,
        verified=row is not None,
        chunk_id=str(row.id) if row is not None else "",
    )


async def _verify_symbol(
    db: AsyncSession,
    repo_id: UUID,
    symbol: str,
) -> CitationCheck:
    # The same rule `dcode_api.routes.internal` resolves a symbol by, from the one
    # place that defines it. This used to be `qualified_name == symbol`, which is
    # stricter than what the tools accept: the indexer builds qualified names from
    # the repository's directory layout (`src.requests.api.get`), so a name written
    # the way anyone writes it verified against nothing. Inside a single request the
    # find-definition tool answered "here it is" and this function answered "that
    # does not exist, strip it".
    #
    # SQL narrows to a superset; `select_symbol_matches` makes the decision, so the
    # preference for an exact match is expressed exactly once.
    rows = (
        (
            await db.execute(
                select(Symbol)
                .where(Symbol.repo_id == repo_id)
                .where(candidate_filter(Symbol.qualified_name, symbol))
            )
        )
        .scalars()
        .all()
    )
    matches = select_symbol_matches(rows, symbol)
    row = matches[0] if matches else None
    if row is None:
        return CitationCheck(symbol=symbol, file_path="", line=0, verified=False)
    return CitationCheck(
        symbol=symbol,
        file_path=row.file_path,
        line=row.line,
        verified=True,
        chunk_id=str(row.chunk_id) if row.chunk_id is not None else "",
    )


# ---------------------------------------------------------------------------
# Enforcement — hard groundedness guardrail
# ---------------------------------------------------------------------------

_REDACTION_MARKER = "[unverified reference removed]"
_REDACTION_MARKER_ZH = "[已移除未验证引用]"


@dataclass
class EnforcedGroundedness:
    """Outcome of applying the hard guardrail to a draft answer."""

    answer: str  # draft with unverified references redacted (+ warning when low)
    citations: list[CitationCheck]  # verified citations only
    score: float  # fraction verified in the ORIGINAL draft (pre-redaction)
    redacted_count: int  # number of unverified references removed


def enforce_groundedness(
    answer: str,
    result: GroundednessResult,
    *,
    threshold: float,
    chinese: bool = False,
) -> EnforcedGroundedness:
    """Apply the groundedness hard guardrail.

    Every unverified reference is redacted from the answer text so an
    unverified code location is never presented as evidence, and only verified
    citations are surfaced. ``score`` stays the pre-redaction fraction (an
    honest measure of the draft), so a heavily redacted answer still scores
    low. A warning footer is appended when ``score`` is below ``threshold``.
    """
    unverified = [check for check in result.citations if not check.verified]
    verified = [check for check in result.citations if check.verified]

    rendered = _render_verified_evidence_ids(answer, verified)
    redacted = _redact_unverified(rendered, unverified, chinese=chinese)
    if result.score < threshold:
        # Two different failures reach this branch and they get different footnotes.
        # An answer with no citations scores 0.0 by convention (see `verify`), and
        # telling the reader "0 unverified references removed" alongside a zero score
        # would be accurate word by word and misleading as a whole — it implies
        # something was stripped. Say which failure it was.
        redacted = (
            _append_uncited_note(redacted, chinese=chinese)
            if not result.citations
            else _append_guardrail_note(
                redacted,
                score=result.score,
                threshold=threshold,
                removed=len(unverified),
                chinese=chinese,
            )
        )

    return EnforcedGroundedness(
        answer=redacted,
        citations=verified,
        score=result.score,
        redacted_count=len(unverified),
    )


def _redact_unverified(
    answer: str,
    unverified: list[CitationCheck],
    *,
    chinese: bool,
) -> str:
    redacted = answer
    marker = _REDACTION_MARKER_ZH if chinese else _REDACTION_MARKER
    for check in unverified:
        if check.source_token:
            redacted = redacted.replace(check.source_token, marker)
        elif check.line > 0 and check.file_path:
            redacted = _replace_file_line_reference(
                redacted,
                f"{check.file_path}:{check.line}",
                marker=marker,
            )
        elif check.symbol:
            redacted = _replace_symbol_reference(redacted, check.symbol, marker=marker)
    return redacted


def _render_verified_evidence_ids(answer: str, verified: list[CitationCheck]) -> str:
    # Models commonly emit compact citation clusters such as ``[C1][C2]``.
    # Insert a separator while the IDs are still unambiguous; replacing them
    # directly would create `` `a.py:1``b.py:2` ``, which Markdown interprets as
    # one malformed code span instead of two clickable citations.
    rendered = re.sub(r"(\[C\d+\])(?=\[C\d+\])", r"\1 ", answer)
    for check in verified:
        if check.source_token and check.display_token:
            rendered = rendered.replace(check.source_token, f"`{check.display_token}`")
    return rendered


def _replace_file_line_reference(text: str, token: str, *, marker: str) -> str:
    """Replace one exact file:line citation, without touching a longer path."""
    escaped = re.escape(token)
    text = re.sub(rf"`{escaped}`", marker, text)
    # Bare form stays supported because FILE_LINE_PATTERN deliberately extracts
    # bare citations. Slashes and hyphens are path characters, so include them
    # in the boundary guards: ``pkg/file.py:1`` must never be rewritten merely
    # because a shorter ``file.py:1`` check failed.
    return re.sub(rf"(?<![\w./-]){escaped}(?![\w./:-])", marker, text)


def _replace_symbol_reference(text: str, token: str, *, marker: str) -> str:
    """Replace the exact backticked symbol that the extractor observed.

    SYMBOL_PATTERN only extracts backticked dotted names. Replacing a bare
    occurrence afterwards is both broader than extraction and unsafe: a failed
    ``hybrid_search.py`` symbol used to corrupt the verified, longer citation
    ``src/retrieval/hybrid_search.py:63``.
    """
    return re.sub(rf"`{re.escape(token)}`", marker, text)


def _append_uncited_note(answer: str, *, chinese: bool) -> str:
    """The footnote for an answer that named no indexed code at all.

    Deliberately says nothing was *checked*, not that anything failed. The score is
    0.0 either way; only this line tells a reader which of the two it was.
    """
    note = (
        "> ⚠️ 此回答没有引用已索引代码，因此其中没有内容经过索引核验；请将其视为未验证回答。"
        if chinese
        else (
            "> ⚠️ This answer cites no indexed code, so nothing in it was checked against "
            "the index. Treat it as unverified rather than as verified."
        )
    )
    body = answer.rstrip()
    return f"{body}\n\n{note}" if body else note


def _append_guardrail_note(
    answer: str,
    *,
    score: float,
    threshold: float,
    removed: int,
    chinese: bool,
) -> str:
    if chinese:
        note = (
            f"> ⚠️ 引用可信度 {score:.2f} 低于 {threshold:.2f} 的保护阈值："
            f"已移除 {removed} 个未在索引中找到的引用。"
        )
    else:
        plural = "s" if removed != 1 else ""
        note = (
            f"> ⚠️ Groundedness {score:.2f} is below the {threshold:.2f} guardrail: "
            f"{removed} unverified reference{plural} removed (not found in the index)."
        )
    body = answer.rstrip()
    return f"{body}\n\n{note}" if body else note
