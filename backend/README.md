# PhotoSort Backend

Stateless FastAPI service that scores batches of photos for blur and exposure using OpenCV. Uploads stay in memory and are never written to disk or a database.

## Setup

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
```

## Run

```powershell
.venv\Scripts\uvicorn app.main:app --reload
```

Interactive docs: http://localhost:8000/docs

```bash
curl -F "files=@img_01.jpg" -F "files=@img_02.png" http://localhost:8000/api/v1/cull-batch
```

## Test & lint

```powershell
.venv\Scripts\pytest
.venv\Scripts\ruff check .
.venv\Scripts\ruff format .
```

## Architecture

```
app/
  main.py               app factory, lifespan (thread pool, analyzers), CORS
  api.py                POST /api/v1/cull-batch (HTTP layer only)
  processing.py         async upload handling, thread-pool fan-out, per-image pipeline
  imaging.py            decode + downsample once -> PreparedImage (proxy, cached gray, luma histogram)
  schemas.py            response models
  config.py             shared settings (upload limits, workers, CORS)
  analyzers/
    base.py             Analyzer interface + AnalysisResult
    registry.py         the list of enabled analyzers
    luma.py             helpers shared by the exposure analyzers
    blur/               Laplacian-variance blur detection (+ its own settings)
    overexposure/       blown-highlight detection from the luma histogram
    underexposure/      crushed-shadow detection from the luma histogram
```

Each upload is decoded **once** into a working proxy (max 1000 px wide). Every registered analyzer then
runs against that proxy, and images are processed concurrently on a shared `ThreadPoolExecutor`.

### Response shape

```json
{
  "batch_id": "6f1c...",
  "total_processed": 2,
  "results": [
    {
      "filename": "img_01.jpg",
      "status": "success",
      "analyses": {
        "blur": {"status": "success", "flag": "SHALLOW_FOCUS", "score": 0.97,
                 "metrics": {"laplacian_variance": 321.8, "subject_sharpness": 2865.6,
                             "background_sharpness": 2.6, "sharp_area": 0.11,
                             "focus_ratio": 1097.8, "subject_tiles": 12.0},
                 "error": null},
        "overexposure": {"status": "success", "flag": "OK", "score": 0.87,
                         "metrics": {"average_brightness": 121.4, "highlight_ratio": 0.0132,
                                     "shadow_ratio": 0.0041},
                         "error": null},
        "underexposure": {"status": "success", "flag": "OK", "score": 0.91,
                          "metrics": {"average_brightness": 121.4, "highlight_ratio": 0.0132,
                                      "shadow_ratio": 0.0041},
                          "error": null}
      },
      "error": null
    },
    {"filename": "broken.jpg", "status": "error", "analyses": {}, "error": "File is corrupted or not a supported image"}
  ]
}
```

- Image-level `error`: the file couldn't be read (wrong type, too large, corrupt).
- Analyzer-level `error`: one analyzer crashed; the other analyzers still report.

### Blur analyzer

A single sharpness number for the whole photo would flag portraits with an intentionally
blurred background, so the analyzer builds a **local sharpness map** instead:

1. Lightly denoise the grayscale proxy (3×3 Gaussian), then take its Laplacian.
2. Split it into a grid (`grid_cols` = 12 columns, rows follow the aspect ratio). Per tile,
   sharpness = Laplacian variance, contrast = intensity std dev.
3. Ignore flat tiles (`contrast < min_tile_contrast`): sky, plain walls and studio backdrops
   look the same in or out of focus.
4. A tile is sharp if its sharpness is ≥ `threshold` (80). The largest 8-connected cluster
   of sharp tiles is the subject, so its position doesn't matter.

| Flag | When |
|---|---|
| `SHARP` | At least `sharp_area_ratio` (50%) of the informative tiles are sharp |
| `SHALLOW_FOCUS` | The subject cluster has ≥ `min_subject_tiles` (2) tiles **and** is ≥ `min_focus_ratio` (4×) sharper than the background median. This is accepted intentional blur. |
| `BLURRY` | Anything else: camera shake, motion blur, missed focus, isolated sharp specks |

`score = s / (s + threshold)`, where `s` is the subject's mean sharpness, or for `BLURRY` the
median tile sharpness. The threshold maps to 0.5, and `BLURRY` always scores below 0.5. Images
too small for the grid, or with no informative tiles, fall back to the old whole-image rule.
Every knob can be overridden with a `PHOTOSORT_BLUR_*` env var. Use the returned `metrics` to
tune them on real photos.

Known limitation: the analyzer can't tell *what* is in focus. If focus landed on the background
and the person is soft, the photo still passes.

### Exposure analyzers

`overexposure` and `underexposure` read one shared 256-bin luma histogram (Y of YCrCb), computed
once per image on `PreparedImage.luma_histogram`. Both report the same metrics: `average_brightness`,
`highlight_ratio` (luma ≥ 250) and `shadow_ratio` (luma ≤ 5).

| Analyzer | Flag | When |
|---|---|---|
| `overexposure` | `OVEREXPOSED` | average brightness > 190 **and** highlight ratio > 10% |
| `underexposure` | `UNDEREXPOSED` | average brightness < 65 **and** shadow ratio > 10% |
| both | `OK` | anything else |

Both conditions are required, so high-key (snow) and low-key (night) shots that keep their detail
aren't flagged. `score` is 0.0-1.0 (higher = better): it is `1 - severity`, where severity is the
smaller of the brightness and clipping severities. Each is 0.5 at its threshold, so flagged photos
score below 0.5 and the rest score 0.5 or more. The thresholds are experimental; tune them with the
returned `metrics`.

## Adding a new analyzer

1. Create `app/analyzers/<name>/` with `analyzer.py`, `settings.py` (a `BaseSettings` with
   `env_prefix="PHOTOSORT_<NAME>_"`), and an `__init__.py` that exports the class.
2. Subclass `Analyzer`: set `name = "<name>"` (it becomes the key under `analyses`) and implement
   `analyze(self, image: PreparedImage) -> AnalysisResult`.
3. Add tests under `tests/analyzers/<name>/`, using the image helpers in `tests/conftest.py`.
4. Register it with one line in `app/analyzers/registry.py`.

Rules for analyzers:
- **Pure and thread-safe.** They run concurrently, so don't mutate shared state or the input image.
- **Don't decode or resize.** Use `image.proxy` (BGR) or `image.gray`. If several analyzers need
  another derived view (e.g. HSV), add it as a `cached_property` on `PreparedImage`.
- **Raise on failure.** The pipeline turns the exception into an error entry for that analyzer only.
- **`score` is 0.0-1.0, higher = better.** Keep flags uppercase (e.g. `OVEREXPOSED`, `SHARP`).
- Keep feature-specific settings in the feature's package, not in `app/config.py`.

## Configuration

Override any setting with an environment variable (or a `.env` file):

| Variable | Default |
|---|---|
| `PHOTOSORT_BLUR_THRESHOLD` | `80.0` |
| `PHOTOSORT_BLUR_GRID_COLS` | `12` |
| `PHOTOSORT_BLUR_MIN_TILE_CONTRAST` | `6.0` |
| `PHOTOSORT_BLUR_SHARP_AREA_RATIO` | `0.5` |
| `PHOTOSORT_BLUR_MIN_SUBJECT_TILES` | `2` |
| `PHOTOSORT_BLUR_MIN_FOCUS_RATIO` | `4.0` |
| `PHOTOSORT_BLUR_DENOISE` | `true` |
| `PHOTOSORT_OVEREXPOSURE_BRIGHTNESS_THRESHOLD` | `190.0` |
| `PHOTOSORT_OVEREXPOSURE_HIGHLIGHT_LEVEL` | `250` |
| `PHOTOSORT_OVEREXPOSURE_HIGHLIGHT_RATIO` | `0.10` |
| `PHOTOSORT_UNDEREXPOSURE_BRIGHTNESS_THRESHOLD` | `65.0` |
| `PHOTOSORT_UNDEREXPOSURE_SHADOW_LEVEL` | `5` |
| `PHOTOSORT_UNDEREXPOSURE_SHADOW_RATIO` | `0.10` |
| `PHOTOSORT_PROXY_MAX_WIDTH` | `1000` |
| `PHOTOSORT_MAX_WORKERS` | CPU count |
| `PHOTOSORT_MAX_FILES_PER_BATCH` | `100` |
| `PHOTOSORT_MAX_FILE_BYTES` | `26214400` (25 MB) |
| `PHOTOSORT_CORS_ORIGINS` | `["http://localhost:5173"]` |
