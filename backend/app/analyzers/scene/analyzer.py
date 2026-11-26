"""Scene description for preset suggestions. Informational only: the flag is always OK and the score 1.0.

Pixel metrics (independent of the user's tuning, so suggestions mean the same under any preset):
- `dark_share`: share of near-black pixels (HSV value <= 0.15). Concerts and night scenes are high.
- `vivid_light`: share of pixels that are both bright and strongly saturated (V >= 0.6, S >= 0.6),
  e.g. colored stage lighting. Concert lights are colored, so they rarely clip to white.
- `soft_texture_share`: share of grid tiles that have structure but no sharp detail (contrast >= 10,
  Laplacian variance < 80). High for out-of-focus crowds and panning streaks behind sports subjects.

EXIF metrics, only when the file carries them (camera originals; web downloads are usually
stripped): `exif_exposure_time` (s), `exif_f_number`, `exif_iso`, `exif_focal_length` (mm),
`exif_focal_length_35mm`, `exif_subject_distance` (m), `exif_macro_lens` (1.0).

Calibrated on the user's test folders (landscapes, birds, concert, sport); see `app/suggest.py`.
"""

import cv2
import numpy as np

from app.analyzers.base import AnalysisResult, Analyzer
from app.analyzers.blur.analyzer import grid_shape, tile_stats
from app.imaging import PreparedImage

DARK_VALUE = 0.15
VIVID_VALUE = 0.6
VIVID_SATURATION = 0.6
GRID_COLS = 12
TEXTURE_CONTRAST = 10.0
SHARP_TILE_VARIANCE = 80.0


class SceneAnalyzer(Analyzer):
    name = "scene"

    def analyze(self, image: PreparedImage) -> AnalysisResult:
        hsv = cv2.cvtColor(image.proxy, cv2.COLOR_BGR2HSV)
        saturation = hsv[..., 1] / 255.0
        value = hsv[..., 2] / 255.0
        metrics = {
            "dark_share": round(float((value <= DARK_VALUE).mean()), 4),
            "vivid_light": round(
                float(((value >= VIVID_VALUE) & (saturation >= VIVID_SATURATION)).mean()), 4
            ),
            "soft_texture_share": round(soft_texture_share(image.gray), 4),
            **{f"exif_{key}": round(v, 6) for key, v in image.exif.items()},
        }
        return AnalysisResult(flag="OK", score=1.0, metrics=metrics)


def soft_texture_share(gray: np.ndarray) -> float:
    """Share of tiles with visible structure but no sharp detail (fixed grid, not user-tunable)."""
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    shape = grid_shape(*denoised.shape, GRID_COLS)
    if shape is None:
        return 0.0
    sharpness, contrast = tile_stats(denoised, cv2.Laplacian(denoised, cv2.CV_64F), *shape)
    soft = (contrast >= TEXTURE_CONTRAST) & (sharpness < SHARP_TILE_VARIANCE)
    return float(soft.mean())
