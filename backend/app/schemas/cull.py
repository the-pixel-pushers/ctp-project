from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Status = Literal["success", "error"]


class AnalysisOut(BaseModel):
    status: Status
    flag: str | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metrics: dict[str, float] = Field(default_factory=dict)
    error: str | None = None


class ImageResult(BaseModel):
    filename: str
    status: Status
    analyses: dict[str, AnalysisOut] = Field(default_factory=dict)
    error: str | None = None


class CullBatchResponse(BaseModel):
    batch_id: UUID
    total_processed: int
    results: list[ImageResult]
