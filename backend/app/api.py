from concurrent.futures import Executor
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.analyzers.base import Analyzer
from app.config import Settings, get_settings
from app.processing import process_batch
from app.schemas import CullBatchResponse

router = APIRouter(prefix="/api/v1", tags=["culling"])


def get_executor(request: Request) -> Executor:
    return request.app.state.executor


def get_analyzers(request: Request) -> list[Analyzer]:
    return request.app.state.analyzers


@router.post("/cull-batch", response_model=CullBatchResponse)
async def cull_batch(
    files: Annotated[
        list[UploadFile],
        # `format: binary` makes Swagger UI (/docs) render a file picker per item
        File(
            description="JPG or PNG images to analyze",
            json_schema_extra={"items": {"type": "string", "format": "binary"}},
        ),
    ],
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
