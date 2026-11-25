import json
from concurrent.futures import Executor
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.analyzers.base import Analyzer
from app.config import Settings, get_settings
from app.processing import process_batch
from app.schemas import CullBatchResponse, PresetSuggestion, SuggestRequest
from app.suggest import suggest_preset
from app.tuning import Catalog, InvalidTuningError, apply_overrides, build_catalog, validate_overrides

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
    client_ids: Annotated[
        list[str] | None,
        Form(description="Optional IDs, one per file in the same order; echoed back as `client_id`"),
    ] = None,
    tuning: Annotated[
        str | None,
        Form(
            description="Optional JSON `{analyzer: {param: value}}` overriding tunable analyzer settings "
            "for this batch only; see `GET /api/v1/settings` for the allowed params and bounds"
        ),
    ] = None,
) -> CullBatchResponse:
    """Run every registered analyzer on each image. Per-image failures are reported inline.
    Each result carries its upload `index` and, if supplied, the matching `client_id`."""
    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Batch exceeds the limit of {settings.max_files_per_batch} files",
        )
    if client_ids is not None and len(client_ids) != len(files):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Got {len(client_ids)} client_ids for {len(files)} files; they must match",
        )
    if tuning:
        try:
            overrides = validate_overrides(json.loads(tuning), analyzers)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="`tuning` is not valid JSON"
            ) from exc
        except InvalidTuningError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        analyzers = apply_overrides(analyzers, overrides)
    return await process_batch(files, analyzers, executor, settings, client_ids)


@router.post("/suggest-preset", response_model=PresetSuggestion | None)
def suggest_batch_preset(request: SuggestRequest) -> PresetSuggestion | None:
    """Best scene preset for a batch of analyzed photos, from the flags and metrics `cull-batch`
    returned (analyzed with default tuning). `null` means no scene stands out: stay on Default."""
    return suggest_preset(request.photos)


@router.get("/settings", response_model=Catalog)
def get_tuning_catalog(analyzers: Annotated[list[Analyzer], Depends(get_analyzers)]) -> Catalog:
    """Tunable parameters (bounds, defaults), sliders and scene presets. Defaults reflect the
    server's configuration, so a client-side Reset is just applying these values."""
    return build_catalog(analyzers)
