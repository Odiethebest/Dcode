"""Canonical Pydantic request and response schemas for cross-service contracts.

This module is the single source of truth for every cross-service payload shape.
Services MUST import these types rather than redefining.
"""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ===========================================================================
# Enums shared by the database, indexing state machine, and API
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
    """AST-level chunk discriminator stored by the index."""

    function = "function"
    method = "method"
    class_ = "class"
    module_doc = "module_doc"


class SymbolKind(StrEnum):
    """Code-graph node kind."""

    function = "function"
    class_ = "class"
    method = "method"
    module = "module"


class EdgeType(StrEnum):
    """Code-graph edge kind."""

    calls = "calls"
    imports = "imports"
    inherits = "inherits"
    references = "references"


# ===========================================================================
# Public indexing API
# ===========================================================================


class RepoCreateRequest(BaseModel):
    """POST /api/v1/repos request body."""

    url: str = Field(..., description="Git URL of the repository to index")


class RepoCreateResponse(BaseModel):
    """POST /api/v1/repos response body (202 Accepted, or 200 OK when reused)."""

    repo_id: UUID
    status: RepoStatus
    reused: bool = Field(
        False,
        description=(
            "True when an existing repo with the same URL was returned instead of "
            "cloning and indexing it again. Nothing was queued."
        ),
    )


class StagesStatus(BaseModel):
    """Per-stage progress block embedded in RepoStatusResponse."""

    cloning: StageState = StageState.pending
    parsing: StageState = StageState.pending
    embedding: StageState = StageState.pending
    graphing: StageState = StageState.pending


class RepoStatusResponse(BaseModel):
    """GET /api/v1/repos/{repo_id}/status response body."""

    repo_id: UUID
    url: str = ""
    status: RepoStatus
    progress: int = Field(0, ge=0, le=100)
    stages: StagesStatus = Field(default_factory=StagesStatus)
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RepoSummary(BaseModel):
    """One row of GET /api/v1/repos."""

    repo_id: UUID
    url: str
    status: RepoStatus


class RepoListResponse(BaseModel):
    """GET /api/v1/repos response body.

    Exists because the workbench had no way to discover what is indexed: the
    switcher read `localStorage` only, so a reader on a new device saw an empty
    product and had to index a repository themselves before they could ask
    anything. `truncated` is explicit rather than implied by a full page —
    silently showing a subset of what exists is the kind of quiet claim this
    project avoids elsewhere.
    """

    repos: list[RepoSummary] = Field(default_factory=list)
    truncated: bool = False


# ===========================================================================
# Public query API (request body; SSE events live in events.py)
# ===========================================================================


class QueryTurn(BaseModel):
    """One prior conversation turn, sent by the client on a follow-up query.

    History is client-supplied on every request (services stay stateless); the
    gateway bounds it before it reaches the planner or the cache key.
    """

    role: Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    """POST /api/v1/query request body."""

    repo_id: UUID
    query: str = Field(..., min_length=1)
    history: list[QueryTurn] = Field(
        default_factory=list,
        description="Prior turns for multi-turn follow-ups (bounded by the gateway).",
    )


# ===========================================================================
# Internal retrieval and graph API
# ===========================================================================


class ScoreComponents(BaseModel):
    """Per-channel scores inside a hybrid search result."""

    model_config = ConfigDict(extra="forbid")

    dense: float
    sparse: float
    rerank: float


class Chunk(BaseModel):
    """A retrieved chunk returned by the internal search API."""

    chunk_id: UUID
    file_path: str
    symbol_name: str
    start_line: int
    end_line: int
    content: str
    score: float
    score_components: ScoreComponents


class Location(BaseModel):
    """Indexed location returned by graph-query endpoints."""

    symbol: str
    file_path: str
    line: int
    chunk_id: UUID | None = None


CallDirection = Literal["callers", "callees", "both"]


class SourceCall(BaseModel):
    """One call expression found in the matched symbol's source chunk.

    ``resolved_target`` is present only when a stored ``calls`` edge on the same
    source line identifies the target. A missing target is intentionally
    represented, rather than silently dropping dynamic/instance calls.
    """

    expression: str
    file_path: str
    line: int
    resolved_target: Location | None = None


class CallNeighbors(BaseModel):
    """Resolved function-call neighbors for the Agent's call-graph tool.

    The location groups keep direction explicit. ``matches`` is retained because
    a short name can resolve to several indexed symbols; callers and callees are
    the union across those disclosed matches. ``source_calls`` keeps expressions
    that the static graph could not resolve instead of silently dropping them.
    """

    found: bool
    symbol: str
    direction: CallDirection
    matches: list[Location] = Field(default_factory=list)
    callers: list[Location] = Field(default_factory=list)
    callees: list[Location] = Field(default_factory=list)
    source_calls: list[SourceCall] = Field(default_factory=list)


class CallPath(BaseModel):
    """A bounded chain of `calls` edges from one symbol to another.

    Architecture questions overwhelmingly ask how control reaches B from A —
    "explain the proxy flow from Session settings to the adapter connection".
    Listing every reference to A answers a different question and buries the
    chain in noise. `nodes` is ordered start → end and each hop is a stored
    `calls` edge, so the path is evidence rather than narration.

    `found=False` with an empty `nodes` is a real answer: within `max_depth`
    there is no static call chain. It is reported rather than smoothed over,
    because the graph's documented blind spots (no type inference, unresolved
    inherited `self.method()`) make absence genuinely common.
    """

    found: bool
    start: str
    end: str
    max_depth: int
    nodes: list[Location] = Field(default_factory=list)
    # Hops actually traversed; `len(nodes) - 1` when found.
    depth: int = 0


# ===========================================================================
# Inspector API (read-only source + call graph — Phase 2 workbench)
# ===========================================================================


class SourceResponse(BaseModel):
    """GET /api/v1/repos/{repo_id}/source response.

    `granularity` records how the source was resolved so the UI renders an
    honest state rather than a cold empty pane. Never 500s: an unresolved
    citation returns found=false / granularity="none".
    """

    found: bool
    granularity: Literal["chunk", "symbol_chunk", "file_outline", "none"]
    file_path: str | None = None
    symbol_name: str | None = None
    chunk_type: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    cited_line: int | None = None
    content: str | None = None
    outline: list[Location] = Field(default_factory=list)
    language: str = "python"


class SymbolNeighbors(BaseModel):
    """GET /api/v1/repos/{repo_id}/neighbors response — call-graph neighbors.

    Each neighbor is a Location (carrying file:line + chunk_id), so the UI can
    click through to its source and walk the graph.
    """

    found: bool
    symbol: str | None = None
    file_path: str | None = None
    line: int | None = None
    called_by: list[Location] = Field(default_factory=list)
    calls: list[Location] = Field(default_factory=list)
    references: list[Location] = Field(default_factory=list)
