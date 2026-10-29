# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

FastAPI service (Python ≥3.12, developed on 3.14) that scores batches of photos for quality. All commands run from this `backend/` directory.

## Commands

Windows venv paths:

```powershell
python -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\uvicorn app.main:app --reload          # http://localhost:8000/docs
.venv\Scripts\pytest                                  # all tests
.venv\Scripts\pytest tests/test_processing.py::test_failing_analyzer_does_not_affect_others   # single test
.venv\Scripts\ruff check . ; .venv\Scripts\ruff format .
```

## Architecture

There is one endpoint, `POST /api/v1/cull-batch` (multipart `files`), and the service is stateless. Uploads are never written to disk: `app/main.py` raises Starlette's `MultiPartParser.spool_max_size` to `max_file_bytes` so files stay in RAM. Keep it that way.

The layout is deliberately flat. Request flow: `app/api.py` (router and dependencies) → `app/processing.py`. There, `process_batch` is async: it reads and validates each upload, then fans images out to the shared `ThreadPoolExecutor` stored on `app.state.executor`. Next comes `run_pipeline`, which is sync and runs inside a worker thread, then `app/imaging.prepare_image`, then every analyzer. Response models live in `app/schemas.py`.

**Pluggable analyzers** (`app/analyzers/`) are the core extension point. Teammates build features such as exposure detection in parallel this way:
- Each analyzer subclasses `Analyzer` (`analyzers/base.py`), sets a unique `name` (it becomes the key under `analyses` in the response) and implements `analyze(PreparedImage) -> AnalysisResult(flag, score, metrics)`.
- Analyzers are enabled by an explicit list in `analyzers/registry.py`, which is built once at startup into `app.state.analyzers`. A new feature should add a package `analyzers/<name>/` (analyzer, settings, `__init__` export) and one line in the registry. It should not need changes to the schema, pipeline or endpoint.
- Analyzers must be pure and thread-safe, must never decode or resize (use `image.proxy` (BGR) or the cached `image.gray`), and should raise on failure. If several analyzers need another derived view, add it as a `cached_property` on `PreparedImage` in `app/imaging.py`.
- `score` is in [0, 1], where higher is better. Flags are uppercase strings (`BLURRY`, `ACCEPTABLE`, …).

**Errors are isolated at two levels.** Never let a single item fail the whole request.
- Image level (`processing._process_one`): wrong type, an oversize file or an undecodable image gives `ImageResult(status="error", error=..., analyses={})`.
- Analyzer level (`processing.run_pipeline`): an analyzer that raises gives `AnalysisOut(status="error")` for that analyzer only, while the others still report.
- Request-level HTTP errors are limited to 413 (more than `max_files_per_batch`) and 422 (no files).

**Settings ownership:** `app/config.py` (`PHOTOSORT_*` env vars) holds only shared settings: proxy width, workers, upload limits, CORS (default `http://localhost:5173`). Feature settings live in the feature's own `BaseSettings` with their own prefix, e.g. `analyzers/blur/settings.py` → `PHOTOSORT_BLUR_THRESHOLD`.

**Blur analyzer:** Laplacian variance of the grayscale proxy (max 1000px wide). Below the threshold (default 80) it is `BLURRY`. `score = var / (var + threshold)`, so the threshold maps to 0.5.

**Planned: exposure.** There will be two separate analyzers, `overexposure` and `underexposure`, each in its own `analyzers/<name>/` package. Both should read one shared luminance histogram, added as a `cached_property` on `PreparedImage`, so it is computed once per image. The frontend filters by flag on the client. Do not add per-feature endpoints.

## Tests

The `tests/` folders mirror `app/`, and per-analyzer tests go in `tests/analyzers/<name>/`. `tests/conftest.py` provides synthetic `sharp_image()`, `blurry_image()` and `encode()` helpers plus a `client` fixture (`TestClient` with the lifespan run). Use these instead of binary fixture files.
