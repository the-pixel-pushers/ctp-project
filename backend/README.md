# PhotoSort Backend

Stateless FastAPI service that scores batches of photos for blur using OpenCV Laplacian variance. Uploads stay in memory and are never written to disk or a database.

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
  imaging.py            decode + downsample once -> PreparedImage (proxy, cached gray)
  analyzers/
    base.py             Analyzer interface + AnalysisResult
    registry.py         the list of enabled analyzers
    blur/               Laplacian-variance blur detection (+ its own settings)
  services/
    pipeline.py         runs every analyzer on one image, isolating failures
    batch_processor.py  async upload handling, thread-pool fan-out
  schemas/cull.py       response models
  api/v1/endpoints/     HTTP layer only
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
        "blur": {"status": "success", "flag": "BLURRY", "score": 0.36,
                 "metrics": {"laplacian_variance": 45.2}, "error": null}
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

Laplacian variance of the grayscale proxy. `variance < 80` → `BLURRY`, otherwise `ACCEPTABLE`.
`score = variance / (variance + threshold)`, so the threshold maps to 0.5 and sharp images approach 1.0.

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
- **`score` is 0.0-1.0, higher = better.** Keep flags uppercase (e.g. `OVEREXPOSED`, `ACCEPTABLE`).
- Keep feature-specific settings in the feature's package, not in `core/config.py`.

## Configuration

Override any setting with an environment variable (or a `.env` file):

| Variable | Default |
|---|---|
| `PHOTOSORT_BLUR_THRESHOLD` | `80.0` |
| `PHOTOSORT_PROXY_MAX_WIDTH` | `1000` |
| `PHOTOSORT_MAX_WORKERS` | CPU count |
| `PHOTOSORT_MAX_FILES_PER_BATCH` | `100` |
| `PHOTOSORT_MAX_FILE_BYTES` | `26214400` (25 MB) |
| `PHOTOSORT_CORS_ORIGINS` | `["http://localhost:5173"]` |
