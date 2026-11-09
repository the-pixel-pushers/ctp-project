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
- `score` is in [0, 1], where higher is better. Flags are uppercase strings (`BLURRY`, `SHARP`, …).

**Errors are isolated at two levels.** Never let a single item fail the whole request.
- Image level (`processing._process_one`): wrong type, an oversize file or an undecodable image gives `ImageResult(status="error", error=..., analyses={})`.
- Analyzer level (`processing.run_pipeline`): an analyzer that raises gives `AnalysisOut(status="error")` for that analyzer only, while the others still report.
- Request-level HTTP errors are limited to 413 (more than `max_files_per_batch`) and 422 (no files).

**Settings ownership:** `app/config.py` (`PHOTOSORT_*` env vars) holds only shared settings: proxy width, workers, upload limits, CORS (default `http://localhost:5173`). Feature settings live in the feature's own `BaseSettings` with their own prefix, e.g. `analyzers/blur/settings.py` → `PHOTOSORT_BLUR_THRESHOLD`.

**Blur analyzer:** builds a local sharpness map, not one global number, so intentional background blur (bokeh portraits) isn't flagged. The grayscale proxy (max 1000px wide) is lightly denoised and passed through a Laplacian, then split into a grid (`grid_cols`, default 12). Per tile it computes Laplacian variance (sharpness) and intensity std (contrast). Flat tiles below `min_tile_contrast` are ignored. Tiles at or above `threshold` (80) are sharp, and the largest 8-connected cluster of sharp tiles is the subject. Flags: `SHARP` if ≥ `sharp_area_ratio` of the informative tiles are sharp; `SHALLOW_FOCUS` if the subject has ≥ `min_subject_tiles` tiles and is ≥ `min_focus_ratio`× sharper than the background median; otherwise `BLURRY`. `score = s / (s + threshold)`, where `s` is the subject's mean sharpness, or the median tile sharpness when the flag is `BLURRY`, so `BLURRY` always scores below 0.5. Images too small for the grid or with no informative tiles fall back to the global variance rule. Synthetic bokeh test images: `soft_background()` and `bokeh_image()` in `tests/conftest.py`. Don't use `blurry_image()` as a background: it blurs to near-uniform gray, which counts as flat.

**Exposure analyzers:** `overexposure` (`OVEREXPOSED`/`OK`) and `underexposure` (`UNDEREXPOSED`/`OK`) are separate packages. Both read `PreparedImage.luma_histogram` (256-bin Y of YCrCb, a `cached_property` computed once per image) through the helpers in `analyzers/luma.py`, and both report the metrics `average_brightness`, `highlight_ratio` (luma ≥ 250) and `shadow_ratio` (luma ≤ 5). A flag needs both a bright (or dark) average and a large clipped share (defaults 190/65 and 10%). `score = 1 - min(brightness severity, clipping severity)`, where each severity is 0.5 at its threshold, so flagged photos score below 0.5. The frontend filters by flag on the client. Do not add per-feature endpoints.

## Tests

The `tests/` folders mirror `app/`, and per-analyzer tests go in `tests/analyzers/<name>/`. `tests/conftest.py` provides synthetic `sharp_image()`, `blurry_image()`, `soft_background()`, `bokeh_image()` and `encode()` helpers plus a `client` fixture (`TestClient` with the lifespan run). Use these instead of binary fixture files.
