import asyncio
import logging
import uuid
from collections.abc import Sequence
from concurrent.futures import Executor
from pathlib import PurePath

from fastapi import UploadFile

from app.analyzers.base import Analyzer
from app.core.config import Settings
from app.imaging import ImageDecodeError
from app.schemas.cull import CullBatchResponse, ImageResult
from app.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)


class InvalidUploadError(ValueError):
    """Raised when an upload fails type or size validation."""


def _validate(filename: str, content_type: str | None, size: int, settings: Settings) -> None:
    extension = PurePath(filename).suffix.lower()
    if extension not in settings.allowed_extensions and content_type not in settings.allowed_content_types:
        raise InvalidUploadError(
            f"Unsupported file type '{extension or content_type}'; only JPG and PNG are accepted"
        )
    if size > settings.max_file_bytes:
        raise InvalidUploadError(f"File exceeds the {settings.max_file_bytes // (1024 * 1024)} MB limit")


async def _process_one(
    file: UploadFile, analyzers: Sequence[Analyzer], executor: Executor, settings: Settings
) -> ImageResult:
    filename = file.filename or "unnamed"
    try:
        data = await file.read()
        _validate(filename, file.content_type, len(data), settings)
        loop = asyncio.get_running_loop()
        analyses = await loop.run_in_executor(
            executor, run_pipeline, data, analyzers, settings.proxy_max_width
        )
        return ImageResult(filename=filename, status="success", analyses=analyses)
    except (InvalidUploadError, ImageDecodeError) as exc:
        return ImageResult(filename=filename, status="error", error=str(exc))
    except Exception:
        logger.exception("Unexpected failure processing %s", filename)
        return ImageResult(filename=filename, status="error", error="Internal error while processing image")
    finally:
        await file.close()


async def process_batch(
    files: list[UploadFile], analyzers: Sequence[Analyzer], executor: Executor, settings: Settings
) -> CullBatchResponse:
    results = await asyncio.gather(*(_process_one(f, analyzers, executor, settings) for f in files))
    return CullBatchResponse(batch_id=uuid.uuid4(), total_processed=len(results), results=list(results))
