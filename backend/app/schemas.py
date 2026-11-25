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
    index: int = Field(ge=0, description="Zero-based position of the file in the upload")
    client_id: str | None = Field(default=None, description="Echo of the ID the client sent for this file")
    filename: str
    status: Status
    analyses: dict[str, AnalysisOut] = Field(default_factory=dict)
    error: str | None = None


class CullBatchResponse(BaseModel):
    batch_id: UUID
    total_processed: int
    results: list[ImageResult]


class PhotoMetrics(BaseModel):
    """One analyzed photo as the client holds it: flag and metrics per analyzer name."""

    flags: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, dict[str, float]] = Field(default_factory=dict)


class SuggestRequest(BaseModel):
    photos: list[PhotoMetrics] = Field(max_length=1000)


class PresetAlternative(BaseModel):
    preset_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class PresetSuggestion(BaseModel):
    preset_id: str
    confidence: float = Field(ge=0.0, le=1.0, description="Share of the batch matching the preset's scene")
    matched: int
    total: int
    reasons: list[str]
    alternatives: list[PresetAlternative] = Field(default_factory=list)
