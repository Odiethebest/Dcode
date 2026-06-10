"""Indexing endpoints — implements DESIGN.md §4.1.

Skeleton: shape-correct stub responses. Real submission and status retrieval
are implemented at milestone M1 per DESIGN.md §2.1.
"""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from dcode_api.deps import get_db
from dcode_shared.schemas import (
    RepoCreateRequest,
    RepoCreateResponse,
    RepoStatus,
    RepoStatusResponse,
    StagesStatus,
    StageState,
)

router = APIRouter(tags=["repos"])


@router.post(
    "/repos",
    response_model=RepoCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_repo(
    body: RepoCreateRequest,
    _: AsyncSession = Depends(get_db),
) -> RepoCreateResponse:
    """Submit a repository for indexing.

    TODO(M1): persist Repo row + publish index job to RabbitMQ
    per DESIGN.md §2.1 (D-2.1.2 async indexing).
    """
    return RepoCreateResponse(repo_id=uuid4(), status=RepoStatus.queued)


@router.get(
    "/repos/{repo_id}/status",
    response_model=RepoStatusResponse,
)
async def repo_status(
    repo_id: UUID,
    _: AsyncSession = Depends(get_db),
) -> RepoStatusResponse:
    """Read indexing progress for a submitted repo.

    TODO(M1): query repos table + Redis `job:{repo_id}` for live progress
    per DESIGN.md §3.3 cache convention.
    """
    return RepoStatusResponse(
        repo_id=repo_id,
        status=RepoStatus.queued,
        progress=0,
        stages=StagesStatus(
            cloning=StageState.pending,
            parsing=StageState.pending,
            embedding=StageState.pending,
            graphing=StageState.pending,
        ),
        error=None,
    )
