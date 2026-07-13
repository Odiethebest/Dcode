"""Question schema for the eval harness."""

from typing import Literal

from pydantic import BaseModel, Field

TaxonomyLabel = Literal["L1", "L2", "L3"]


class GroundTruthTarget(BaseModel):
    file_path: str = Field(..., min_length=1)
    symbol_name: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class EvalQuestion(BaseModel):
    id: str = Field(..., min_length=1)
    repo_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    taxonomy: TaxonomyLabel
    gt_chunk_ids: list[str] = Field(default_factory=list)
    gt_targets: list[GroundTruthTarget] = Field(default_factory=list)
    gt_files: list[str]
    source: str = Field(..., min_length=1)
