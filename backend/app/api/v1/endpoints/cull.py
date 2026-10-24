from concurrent.futures import Executor
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.analyzers.base import Analyzer
from app.api.deps import get_analyzers, get_executor
from app.core.config import Settings, get_settings
from app.schemas.cull import CullBatchResponse
from app.services.batch_processor import process_batch

router = APIRouter(tags=["culling"])


@router.post("/cull-batch", response_model=CullBatchResponse)
async def cull_batch(
    files: Annotated[list[UploadFile], File(description="JPG or PNG images to analyze")],
    analyzers: Annotated[list[Analyzer], Depends(get_analyzers)],
    executor: Annotated[Executor, Depends(get_executor)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CullBatchResponse:
    """Run every registered analyzer on each image. Per-image failures are reported inline."""
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Batch exceeds the limit of {settings.max_files_per_batch} files",
        )
    return await process_batch(files, analyzers, executor, settings)
