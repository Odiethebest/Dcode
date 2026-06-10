"""Pydantic request / response schemas — implements DESIGN.md §4 (Interface Contracts).

This module is the single source of truth for every cross-service payload shape.
Services MUST import these types rather than redefining.
"""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ===========================================================================
# Enums (DESIGN.md §3.2 repos.status / §2.1 state machine)
# ===========================================================================


class RepoStatus(StrEnum):
    """Index pipeline state — monotonically advances except to `failed`."""

    queued = "queued"
    cloning = "cloning"
    parsing = "parsing"
    embedding = "embedding"
    graphing = "graphing"
    ready = "ready"
    failed = "failed"


class StageState(StrEnum):
    """Per-stage state inside the indexing pipeline."""

    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"


class ChunkType(StrEnum):
    """AST-level chunk discriminator (DESIGN.md §3.2 chunks.chunk_type)."""

    function = "function"
    method = "method"
    class_ = "class"
    module_doc = "module_doc"


class SymbolKind(StrEnum):
    """Code-graph node kind (DESIGN.md §3.2 symbols.kind)."""

    function = "function"
    class_ = "class"
    method = "method"
    module = "module"


class EdgeType(StrEnum):
    """Code-graph edge kind (DESIGN.md §3.2 edges.edge_type)."""

    calls = "calls"
    imports = "imports"
    inherits = "inherits"
    references = "references"


# ===========================================================================
# Indexing API (DESIGN.md §4.1)
# ===========================================================================


class RepoCreateRequest(BaseModel):
    """POST /api/v1/repos request body."""

    url: str = Field(..., description="Git URL of the repository to index")


class RepoCreateResponse(BaseModel):
    """POST /api/v1/repos response body (202 Accepted)."""

    repo_id: UUID
    status: RepoStatus


class StagesStatus(BaseModel):
    """Per-stage progress block embedded in RepoStatusResponse."""

    cloning: StageState = StageState.pending
    parsing: StageState = StageState.pending
    embedding: StageState = StageState.pending
    graphing: StageState = StageState.pending


class RepoStatusResponse(BaseModel):
    """GET /api/v1/repos/{repo_id}/status response body."""

    repo_id: UUID
    status: RepoStatus
    progress: int = Field(0, ge=0, le=100)
    stages: StagesStatus = Field(default_factory=StagesStatus)
    error: str | None = None


# ===========================================================================
# Query API (DESIGN.md §4.3 — request body; SSE events live in events.py)
# ===========================================================================


class QueryRequest(BaseModel):
    """POST /api/v1/query request body."""

    repo_id: UUID
    query: str = Field(..., min_length=1)


# ===========================================================================
# Internal retrieval & graph API (DESIGN.md §4.2)
# ===========================================================================


class ScoreComponents(BaseModel):
    """Per-channel scores inside a hybrid search result."""

    model_config = ConfigDict(extra="forbid")

    dense: float
    sparse: float
    rerank: float


class Chunk(BaseModel):
    """A retrieved chunk (DESIGN.md §4.2 search return shape)."""

    chunk_id: UUID
    file_path: str
    symbol_name: str
    start_line: int
    end_line: int
    content: str
    score: float
    score_components: ScoreComponents


class Location(BaseModel):
    """Graph-query result shape (DESIGN.md §4.2)."""

    symbol: str
    file_path: str
    line: int
    chunk_id: UUID | None = None
