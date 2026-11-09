"""Blur detection via a local Laplacian-variance sharpness map.

A single global Laplacian variance averages sharpness over the whole frame, so a portrait
with a sharp subject and an intentionally blurred background reads as BLURRY. Instead the
image is split into a grid of tiles and we ask *where* the sharpness is:

- SHARP: most of the informative (non-flat) tiles are sharp.
- SHALLOW_FOCUS: a contiguous cluster of sharp tiles (the subject) stands out clearly from
  a soft background, e.g. bokeh portraits. Position and size of the subject don't matter.
- BLURRY: nothing is clearly in focus (camera shake, motion blur, missed focus).

Flat tiles (sky, plain walls, studio backdrops) carry no focus information and are ignored.
Images too small for the grid, or with no informative tiles, fall back to the global rule.
"""

import cv2
import numpy as np

from app.analyzers.base import AnalysisResult, Analyzer
from app.analyzers.blur.settings import BlurSettings
from app.imaging import PreparedImage

MIN_TILE_PX = 8  # below this a tile has too few pixels for a meaningful variance
BACKGROUND_FLOOR = 1.0  # avoids dividing by ~0 when the background is perfectly smooth


def laplacian_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def normalize_score(variance: float, threshold: float) -> float:
    """Map variance to [0, 1] with a saturating curve where `threshold` maps to 0.5."""
    if variance <= 0:
        return 0.0
    score = variance / (variance + threshold)
    return round(min(max(score, 0.0), 1.0), 4)


def grid_shape(height: int, width: int, grid_cols: int) -> tuple[int, int] | None:
    """(rows, cols) giving roughly square tiles, or None if the image is too small."""
    cols = grid_cols
    rows = max(1, round(grid_cols * height / width))
    if width // cols < MIN_TILE_PX or height // rows < MIN_TILE_PX:
        return None
    return rows, cols


def tile_stats(
    gray: np.ndarray, laplacian: np.ndarray, rows: int, cols: int
) -> tuple[np.ndarray, np.ndarray]:
    """Per-tile Laplacian variance (sharpness) and intensity std dev (contrast), shape (rows, cols)."""
    height, width = gray.shape
    ys = np.linspace(0, height, rows + 1, dtype=int)
    xs = np.linspace(0, width, cols + 1, dtype=int)
    sharpness = np.empty((rows, cols), dtype=np.float64)
    contrast = np.empty((rows, cols), dtype=np.float64)
    for r in range(rows):
        for c in range(cols):
            window = (slice(ys[r], ys[r + 1]), slice(xs[c], xs[c + 1]))
            sharpness[r, c] = laplacian[window].var()
            contrast[r, c] = gray[window].std()
    return sharpness, contrast


def largest_cluster(mask: np.ndarray) -> np.ndarray:
    """Boolean mask of the largest 8-connected True region (all False if there is none)."""
    if not mask.any():
        return np.zeros_like(mask, dtype=bool)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    biggest = 1 + int(np.argmax(stats[1:count, cv2.CC_STAT_AREA]))  # label 0 is background
    return labels == biggest


class BlurAnalyzer(Analyzer):
    name = "blur"

    def __init__(self, settings: BlurSettings | None = None) -> None:
        self.settings = settings or BlurSettings()

    def analyze(self, image: PreparedImage) -> AnalysisResult:
        s = self.settings
        gray = image.gray
        if s.denoise:
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        global_variance = float(laplacian.var())

        shape = grid_shape(*gray.shape, s.grid_cols)
        if shape is None:
            return self._global_result(global_variance)

        sharpness, contrast = tile_stats(gray, laplacian, *shape)
        informative = contrast >= s.min_tile_contrast
        informative_count = int(informative.sum())
        if informative_count == 0:
            return self._global_result(global_variance)

        sharp = informative & (sharpness >= s.threshold)
        subject = largest_cluster(sharp)
        subject_tiles = int(subject.sum())
        background = informative & ~sharp

        sharp_area = float(sharp.sum()) / informative_count
        background_sharpness = float(np.median(sharpness[background])) if background.any() else 0.0
        if subject_tiles:
            subject_sharpness = float(sharpness[subject].mean())
        else:
            subject_sharpness = float(sharpness[informative].max())
        focus_ratio = subject_sharpness / max(background_sharpness, BACKGROUND_FLOOR)

        if sharp_area >= s.sharp_area_ratio:
            flag, score_basis = "SHARP", subject_sharpness
        elif subject_tiles >= s.min_subject_tiles and focus_ratio >= s.min_focus_ratio:
            flag, score_basis = "SHALLOW_FOCUS", subject_sharpness
        else:
            # Fewer than half the informative tiles are sharp, so this median is below the
            # threshold and the score stays under 0.5 even if a stray tile is sharp.
            flag, score_basis = "BLURRY", float(np.median(sharpness[informative]))

        return AnalysisResult(
            flag=flag,
            score=normalize_score(score_basis, s.threshold),
            metrics={
                "laplacian_variance": round(global_variance, 2),
                "subject_sharpness": round(subject_sharpness, 2),
                "background_sharpness": round(background_sharpness, 2),
                "sharp_area": round(sharp_area, 4),
                "focus_ratio": round(focus_ratio, 2),
                "subject_tiles": float(subject_tiles),
            },
        )

    def _global_result(self, variance: float) -> AnalysisResult:
        """Old whole-image rule, for images the tile grid can't say anything about."""
        is_sharp = variance >= self.settings.threshold
        return AnalysisResult(
            flag="SHARP" if is_sharp else "BLURRY",
            score=normalize_score(variance, self.settings.threshold),
            metrics={
                "laplacian_variance": round(variance, 2),
                "subject_sharpness": round(variance, 2),
                "background_sharpness": 0.0,
                "sharp_area": 1.0 if is_sharp else 0.0,
                "focus_ratio": 1.0,
                "subject_tiles": 0.0,
            },
        )
