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
- Request-level HTTP errors are limited to 413 (more than `max_files_per_batch`) and 422 (no files, or `client_ids` length differing from `files`).

**Result identity:** every `ImageResult` carries `index` (upload position, always set) and `client_id` (echo of the optional `client_ids` form field). Match results to files with these, never `filename`, which can repeat. Set them on every return path in `_process_one`, including errors. The frontend keeps the original `File` objects and exports the kept ones itself, so the backend never stores or returns image bytes.

**Settings ownership:** `app/config.py` (`PHOTOSORT_*` env vars) holds only shared settings: proxy width, workers, upload limits, CORS (default `http://localhost:5173`). Feature settings live in the feature's own `BaseSettings` with their own prefix, e.g. `analyzers/blur/settings.py` → `PHOTOSORT_BLUR_THRESHOLD`.

**Blur analyzer:** builds a local sharpness map, not one global number, so intentional background blur (bokeh portraits) isn't flagged. The grayscale proxy (max 1000px wide) is lightly denoised and passed through a Laplacian, then split into a grid (`grid_cols`, default 12). Per tile it computes Laplacian variance (sharpness) and intensity std (contrast). Flat tiles below `min_tile_contrast` are ignored. Tiles at or above `threshold` (80) are sharp, and the largest 8-connected cluster of sharp tiles is the subject. Flags: `SHARP` if ≥ `sharp_area_ratio` (0.40) of the informative tiles are sharp; `SHALLOW_FOCUS` if the subject has ≥ `min_subject_tiles` tiles, holds ≥ `min_subject_cluster_share` (0.5) of all sharp tiles (rejects scattered specks; waived when the cluster has ≥ `confident_subject_tiles` (5) tiles, since smooth skin fragments real subjects), and is ≥ `min_focus_ratio`× (default 20) sharper than the background median and its mean sharpness is ≥ `min_shallow_subject_sharpness` (100); a lone sharp tile (the only one in the frame) also counts as the subject when its ratio is ≥ `min_single_tile_focus_ratio` (40); otherwise `BLURRY`. Between the `SHARP` and `SHALLOW_FOCUS` checks sits an optional **sharp-region rule**: `SHARP` when the subject cluster covers ≥ `min_sharp_region_area` of the informative tiles, its mean sharpness is ≥ `min_sharp_region_sharpness` and it holds ≥ `min_subject_cluster_share` of the sharp tiles. It is off by default (`min_sharp_region_area` = 1.0) and is enabled by the "Sky & smooth areas" slider and the Landscape preset. Why it exists: on 4,319 real landscapes, big smooth areas (sky, calm water, snow, sand) pass the contrast test yet have no detail, so they diluted `sharp_area` and good photos fell to `BLURRY` (30%) or were misread as `SHALLOW_FOCUS`. Ignoring them (`min_tile_contrast` 10) plus the rule (area 0.05, sharpness 130) cut false `BLURRY` to ~17% while still catching ~97% of mild defocus and ~70% of camera shake (81% on defaults). `score = s / (s + threshold)`, where `s` is the subject's mean sharpness, or the median tile sharpness when the flag is `BLURRY`, so `BLURRY` always scores below 0.5. Images too small for the grid or with no informative tiles fall back to the global variance rule. The blur metrics also include two tuning-independent scene metrics: `top_detail_ratio` (Laplacian variance of the top third ÷ the bottom third) and `top_brightness_gain` (top-third mean luma − bottom third), used to spot open sky. Synthetic test images: `soft_background()`, `bokeh_image()` and `landscape_image()` (smooth sky over detail) in `tests/conftest.py`. Don't use `blurry_image()` as a background: it blurs to near-uniform gray, which counts as flat.

**Exposure analyzers:** `overexposure` (`OVEREXPOSED`/`OK`) and `underexposure` (`UNDEREXPOSED`/`OK`) are separate packages. Both read `PreparedImage.luma_histogram` (256-bin Y of YCrCb, a `cached_property` computed once per image) through the helpers in `analyzers/luma.py`, and both report the metrics `average_brightness`, `highlight_ratio` (luma ≥ 250) and `shadow_ratio` (luma ≤ 5). A flag needs both a bright (or dark) average and a large clipped share (defaults 160/80 and 6%). `score = 1 - min(brightness severity, clipping severity)`, where each severity is 0.5 at its threshold, so flagged photos score below 0.5. The frontend filters by flag on the client. Do not add per-feature endpoints.

**User tuning:** `app/tuning.py` declares which analyzer settings are user-editable (`PARAMS`, with bounds), plus plain-language `SLIDERS` (each slider's `default_level` = shipped defaults; most have 5 levels with the default at 2) and scene `PRESETS`. `GET /api/v1/settings` returns this catalog with live defaults (the single source of truth, so frontend Reset just re-applies them). `POST /cull-batch` accepts an optional `tuning` form field (JSON `{analyzer: {param: value}}`); it is validated (unknown/locked params, bounds, `min_shallow_subject_sharpness >= threshold`, `confident_subject_tiles >= min_subject_tiles`, `min_sharp_region_sharpness >= threshold`; 422 on failure) and applied per request through `Analyzer.with_overrides`, which builds new analyzers and never mutates the shared startup ones. Locked on purpose: shared limits in `config.py`, `MIN_TILE_PX`, `BACKGROUND_FLOOR`, the kernel, connectivity and blur `denoise`. A new analyzer opts in by adding a `PARAMS` entry (and optionally sliders).

**Preset suggestion:** `app/suggest.py` predicts the best scene preset for a batch. `POST /api/v1/suggest-preset` takes `{photos: [{flags, metrics}]}` (what `cull-batch` returned, up to 1000) and returns a `PresetSuggestion` (`preset_id`, `confidence`, `reasons`, `alternatives`) or `null`. Each photo becomes boolean indicators (dark, crushed, bright, blown, point lights, tiny/small subject on a soft background, open sky: `top_detail_ratio` < 0.5 and `top_brightness_gain` > 0); each `Rule` maps indicators to one scene preset, scored by the share of the batch that matches. A preset needs ≥ 3 photos and ≥ 40% of the batch; ties go to the earlier rule. Only scene presets are eligible (never default, strict/lenient cull, sports or macro). Blur metrics depend on tuning, so the thresholds assume default settings and the frontend only asks for batches analyzed with defaults. Calibrate thresholds on real folders with `.venv\Scripts\python -m scripts.suggest_report <folder>`.

## Tests

The `tests/` folders mirror `app/`, and per-analyzer tests go in `tests/analyzers/<name>/`. `tests/conftest.py` provides synthetic `sharp_image()`, `blurry_image()`, `soft_background()`, `bokeh_image()` and `encode()` helpers plus a `client` fixture (`TestClient` with the lifespan run). Use these instead of binary fixture files.
