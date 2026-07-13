"""Resolve stable ground-truth anchors to chunk ids for the current index."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from dcode_shared.db.models import Chunk as DBChunk
from dcode_shared.db.session import SessionLocal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dcode_eval.questions.models import EvalQuestion, GroundTruthTarget


async def resolve_questions(
    questions: Sequence[EvalQuestion],
    *,
    repo_id_override: str | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
) -> list[EvalQuestion]:
    """Return questions with effective repo ids and current-index GT chunk ids.

    Existing fixtures with stored ``gt_chunk_ids`` continue to run without a
    database lookup. Passing ``--repo-id`` opts into stable target resolution.
    """
    if not _needs_resolution(questions, repo_id_override):
        return list(questions)

    resolved: list[EvalQuestion] = []
    async with session_factory() as session:
        for question in questions:
            effective_repo_id = repo_id_override or question.repo_id
            if not question.gt_targets:
                raise ValueError(
                    f"question {question.id} cannot be run with repo override "
                    "because it has no gt_targets"
                )
            gt_chunk_ids = await resolve_targets(
                session,
                repo_id=effective_repo_id,
                question_id=question.id,
                targets=question.gt_targets,
            )
            resolved.append(
                question.model_copy(
                    update={"repo_id": effective_repo_id, "gt_chunk_ids": gt_chunk_ids}
                )
            )
    return resolved


async def resolve_targets(
    session: AsyncSession,
    *,
    repo_id: str,
    question_id: str,
    targets: Sequence[GroundTruthTarget],
) -> list[str]:
    repo_uuid = _parse_repo_id(repo_id)
    resolved: list[str] = []
    for target in targets:
        result = await session.execute(
            select(DBChunk)
            .where(DBChunk.repo_id == repo_uuid)
            .where(DBChunk.file_path == target.file_path)
            .order_by(DBChunk.start_line, DBChunk.end_line)
        )
        chunk_id = _select_target_chunk(question_id, target, list(result.scalars().all()))
        if chunk_id not in resolved:
            resolved.append(chunk_id)
    return resolved


def _needs_resolution(
    questions: Sequence[EvalQuestion],
    repo_id_override: str | None,
) -> bool:
    if repo_id_override is not None:
        return True
    return any(question.gt_targets and not question.gt_chunk_ids for question in questions)


def _select_target_chunk(
    question_id: str,
    target: GroundTruthTarget,
    candidates: Sequence[Any],
) -> str:
    matches = [candidate for candidate in candidates if _matches_target(candidate, target)]
    exact_start = [
        candidate
        for candidate in matches
        if target.start_line is not None and candidate.start_line == target.start_line
    ]

    if len(exact_start) == 1:
        return str(exact_start[0].id)
    if len(matches) == 1:
        return str(matches[0].id)
    if not matches:
        raise ValueError(
            f"question {question_id} target did not match any chunk: "
            f"{target.model_dump(exclude_none=True)}"
        )

    formatted = ", ".join(
        f"{candidate.symbol_name}@{candidate.start_line}-{candidate.end_line}"
        for candidate in matches[:5]
    )
    raise ValueError(
        f"question {question_id} target is ambiguous: "
        f"{target.model_dump(exclude_none=True)} matched {formatted}"
    )


def _matches_target(candidate: Any, target: GroundTruthTarget) -> bool:
    if candidate.file_path != target.file_path:
        return False
    if target.symbol_name is not None and candidate.symbol_name != target.symbol_name:
        return False
    if target.start_line is not None and not (
        candidate.start_line <= target.start_line <= candidate.end_line
    ):
        return False
    return not (
        target.end_line is not None
        and not (candidate.start_line <= target.end_line <= candidate.end_line)
    )


def _parse_repo_id(repo_id: str) -> UUID:
    try:
        return UUID(repo_id)
    except ValueError as exc:
        raise ValueError(f"repo_id must be a UUID when resolving gt_targets: {repo_id}") from exc
