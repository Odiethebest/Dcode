"""Question schema for the eval harness."""

from typing import Literal

from pydantic import BaseModel, Field

TaxonomyLabel = Literal["L1", "L2", "L3"]


class EvalQuestion(BaseModel):
    id: str = Field(..., min_length=1)
    repo_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    taxonomy: TaxonomyLabel
    gt_chunk_ids: list[str]
    gt_files: list[str]
    source: str = Field(..., min_length=1)
