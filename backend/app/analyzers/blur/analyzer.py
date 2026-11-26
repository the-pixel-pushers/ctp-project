"""Blur detection via a local Laplacian-variance sharpness map.

A single global Laplacian variance averages sharpness over the whole frame, so a portrait
with a sharp subject and an intentionally blurred background reads as BLURRY. Instead the
image is split into a grid of tiles and we ask *where* the sharpness is:

- SHARP: most of the informative (non-flat) tiles are sharp.
- SHALLOW_FOCUS: a contiguous cluster of sharp tiles (the subject) stands out clearly from
  a soft background, e.g. bokeh portraits, and is itself clearly sharp in absolute terms.
  The cluster must hold at least `min_subject_cluster_share` of all sharp tiles (so scattered
  specks on a soft frame don't count) unless it is big (`confident_subject_tiles`). Position and
  size of the subject don't matter. A single sharp tile (the only one in the frame) also counts
  when it stands out very strongly (`min_single_tile_focus_ratio`).
- SHARP (sharp-region rule, off by default): a large enough, clearly sharp cluster while the rest of
  the frame is merely textureless (open sky, calm water, snow). Enabled for landscapes.
- Face override (off by default, Portrait preset): when a face is detected, its sharpness decides.
  Smooth, dim skin reads as soft at tile level, while bright bokeh discs read as sharp, so without
  this the brightest bokeh patch becomes "the subject" and the real one is ignored.
- BLURRY: nothing is clearly in focus (camera shake, motion blur, missed focus), *and* the edges
  are soft under the re-blur measure. A tile-level BLURRY whose edges stay crisp (smooth scene with
  little texture, heavy JPEG) is rescued as SHARP (`min_reblur_sharpness`).

Flat tiles (sky, plain walls, studio backdrops) carry no focus information and are ignored.
Images too small for the grid, or with no informative tiles, fall back to the global rule.
"""

import cv2
import numpy as np

from app.analyzers.base import AnalysisResult, Analyzer
from app.analyzers.blur.settings import BlurSettings
from app.imaging import PreparedImage

MIN_FACE_WIDTH = 0.05  # faces narrower than this share of the frame are background people/false hits
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


def scene_metrics(gray: np.ndarray, laplacian: np.ndarray) -> dict[str, float]:
    """Top-third vs bottom-third detail and brightness. Independent of tuning; a smooth, brighter
    top above a detailed bottom is the signature of open sky (used for landscape suggestions)."""
    height = gray.shape[0]
    third = max(1, height // 3)
    top, bottom = slice(0, third), slice(height - third, height)
    top_detail = float(laplacian[top].var())
    bottom_detail = float(laplacian[bottom].var())
    return {
        "top_detail_ratio": round(top_detail / max(bottom_detail, BACKGROUND_FLOOR), 4),
        "top_brightness_gain": round(float(gray[top].mean()) - float(gray[bottom].mean()), 2),
    }


REBLUR_KERNEL = 9  # box blur length for the re-blur measure (Crete et al. 2007)
EDGE_SMOOTH_SIGMA = 1.0  # light smoothing that removes sensor noise but keeps (even blurred) edges
EDGE_MIN_STEP = 3.0  # gray levels per pixel the smoothed image must change by to count as an edge
# The rescue needs edges spread over the frame: a tile "has edges" when >= 2% of its pixels are
# edge pixels, and at least this share of the 12-column grid's tiles must. A few crisp specks on an
# otherwise edgeless soft frame don't make a sharp photo. On the 133 hand-checked landscapes the 1st
# percentile was 0.33; isolated-speck test frames sit at 0.04-0.22.
EDGE_TILE_PIXEL_SHARE = 0.02
MIN_EDGE_COVERAGE = 0.25
COVERAGE_GRID_COLS = 12
# Heavy sensor noise is crisp at the pixel level and survives the edge smoothing, so the rescue is
# skipped above this estimated noise sigma (gray levels) and the tile verdict stands. The 133
# hand-checked landscapes peaked at 2.5; a soft frame with sigma-8 noise reads 8.2.
MAX_RESCUE_NOISE = 5.0
_NOISE_KERNEL = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float64)
_NOISE_KERNEL_NORM = 6.0  # sqrt of the kernel's sum of squares (36)


def noise_sigma(gray: np.ndarray) -> float:
    """Noise standard deviation from the Immerkaer (1996) operator, using the median response
    (robust): edges and texture are a minority of pixels, so unlike the mean-based form they barely
    move it. A richly textured sharp photo must not look 'noisy' and lose its rescue."""
    height, width = gray.shape
    if height < 3 or width < 3:
        return 0.0
    response = np.abs(cv2.filter2D(gray.astype(np.float64), -1, _NOISE_KERNEL))[1:-1, 1:-1]
    return float(np.median(response) / (0.6745 * _NOISE_KERNEL_NORM))  # MAD -> sigma


def edge_mask(gray: np.ndarray) -> np.ndarray:
    """Pixels on a real edge (in either direction) that survives light smoothing."""
    smooth = cv2.GaussianBlur(gray.astype(np.float64), (0, 0), EDGE_SMOOTH_SIGMA)
    mask = np.zeros(gray.shape, dtype=bool)
    mask[:-1, :] |= np.abs(np.diff(smooth, axis=0)) >= EDGE_MIN_STEP
    mask[:, :-1] |= np.abs(np.diff(smooth, axis=1)) >= EDGE_MIN_STEP
    return mask


def edge_coverage(gray: np.ndarray) -> float:
    """Share of grid tiles that contain real edges (1.0/0.0 for images too small for the grid)."""
    mask = edge_mask(gray)
    shape = grid_shape(*gray.shape, COVERAGE_GRID_COLS)
    if shape is None:
        return 1.0 if mask.any() else 0.0
    rows, cols = shape
    ys = np.linspace(0, gray.shape[0], rows + 1, dtype=int)
    xs = np.linspace(0, gray.shape[1], cols + 1, dtype=int)
    with_edges = sum(
        mask[ys[r] : ys[r + 1], xs[c] : xs[c + 1]].mean() >= EDGE_TILE_PIXEL_SHARE
        for r in range(rows)
        for c in range(cols)
    )
    return with_edges / (rows * cols)


def reblur_sharpness(gray: np.ndarray) -> float:
    """Edge crispness that doesn't depend on how much texture a photo has, in [0, 1] (higher = sharper).

    Re-blur the image along each axis and measure how much of the neighbour-pixel variation survives
    (Crete et al. 2007, "The blur effect"). Crisp edges lose a lot when re-blurred; edges that are
    already blurred barely change. Smooth scenes with a few crisp edges (hills against the sky,
    dunes, long-exposure water) therefore still score high, unlike Laplacian variance, which only
    measures the amount of fine detail.

    Only real edges are measured: pixels whose step survives a light Gaussian smoothing. Sensor
    noise is crisp at the pixel level and would otherwise make a blurred, noisy photo look sharp.
    No edges at all (flat, or noise on soft shapes) gives 0."""
    f = gray.astype(np.float64)
    smooth = cv2.GaussianBlur(f, (0, 0), EDGE_SMOOTH_SIGMA)  # same smoothing as `edge_mask`
    blur_effect = 0.0
    for axis in (0, 1):
        ksize = (1, REBLUR_KERNEL) if axis == 0 else (REBLUR_KERNEL, 1)  # cv2 takes (width, height)
        reblurred = cv2.blur(f, ksize)
        edges = np.abs(np.diff(smooth, axis=axis)) >= EDGE_MIN_STEP
        d_orig = np.abs(np.diff(f, axis=axis))[edges]
        d_blur = np.abs(np.diff(reblurred, axis=axis))[edges]
        total = d_orig.sum()
        if total <= 0:
            return 0.0
        lost = np.maximum(0.0, d_orig - d_blur).sum()
        blur_effect = max(blur_effect, (total - lost) / total)
    return 1.0 - blur_effect


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
        # On the raw gray: the analyzer's denoise step would soften the very edges being measured.
        rb = reblur_sharpness(image.gray)
        coverage = edge_coverage(image.gray)
        noise = noise_sigma(image.gray)
        extra = {
            "reblur_sharpness": round(rb, 4),
            "edge_coverage": round(coverage, 4),
            "noise_level": round(noise, 2),
        }
        result = self._rescue(self._analyze_tiles(image, extra), rb, coverage, noise)
        return self._face_override(image, result)

    def _face_override(self, image: PreparedImage, result: AnalysisResult) -> AnalysisResult:
        """In a portrait the face is the subject: if one is detected, its sharpness decides between
        BLURRY and not. Runs after the re-blur rescue so crisp bokeh edges can't rescue a soft face."""
        cutoff = self.settings.face_sharpness
        if cutoff <= 0:
            return result
        width = image.proxy.shape[1]
        face = next((f for f in image.faces if f.width >= MIN_FACE_WIDTH * width), None)
        if face is None:
            return result
        gray = image.gray[face.y : face.y + face.height, face.x : face.x + face.width]
        if self.settings.denoise:
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
        face_sharpness = laplacian_variance(gray)
        metrics = {**result.metrics, "face_sharpness": round(face_sharpness, 2)}
        score = normalize_score(face_sharpness, cutoff)
        if face_sharpness < cutoff:
            return AnalysisResult(flag="BLURRY", score=score, metrics=metrics)
        if result.flag == "BLURRY":
            return AnalysisResult(flag="SHALLOW_FOCUS", score=score, metrics=metrics)
        return AnalysisResult(flag=result.flag, score=result.score, metrics=metrics)

    def _rescue(self, result: AnalysisResult, rb: float, coverage: float, noise: float) -> AnalysisResult:
        """BLURRY needs both a weak tile verdict *and* soft edges. Edges that stay crisp under
        re-blurring, spread over the frame, mean the photo is sharp, just low in texture (smooth
        scenes, heavy JPEG). Not applied to very noisy images, where noise fakes crispness."""
        cutoff = self.settings.min_reblur_sharpness
        if (
            result.flag != "BLURRY"
            or cutoff <= 0
            or rb < cutoff
            or coverage < MIN_EDGE_COVERAGE
            or noise > MAX_RESCUE_NOISE
        ):
            return result
        score = round(min(1.0, 0.5 + 0.5 * (rb - cutoff) / (1.0 - cutoff)), 4)
        return AnalysisResult(flag="SHARP", score=score, metrics=result.metrics)

    def _analyze_tiles(self, image: PreparedImage, extra: dict[str, float]) -> AnalysisResult:
        s = self.settings
        gray = image.gray
        if s.denoise:
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        global_variance = float(laplacian.var())
        scene = {**scene_metrics(gray, laplacian), **extra}

        shape = grid_shape(*gray.shape, s.grid_cols)
        if shape is None:
            return self._global_result(global_variance, scene)

        sharpness, contrast = tile_stats(gray, laplacian, *shape)
        informative = contrast >= s.min_tile_contrast
        informative_count = int(informative.sum())
        if informative_count == 0:
            return self._global_result(global_variance, scene)

        sharp = informative & (sharpness >= s.threshold)
        subject = largest_cluster(sharp)
        subject_tiles = int(subject.sum())
        total_sharp = int(sharp.sum())
        lone_sharp_tile = total_sharp == 1  # one sharp tile in the whole frame, not scattered specks
        cluster_share = subject_tiles / total_sharp if total_sharp else 0.0
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
        elif (
            subject_tiles / informative_count >= s.min_sharp_region_area
            and subject_sharpness >= s.min_sharp_region_sharpness
            and cluster_share >= s.min_subject_cluster_share
        ):
            # A clearly sharp region, with the rest of the frame merely textureless (sky, water),
            # not defocused. Checked before SHALLOW_FOCUS so smooth skies aren't read as bokeh.
            flag, score_basis = "SHARP", subject_sharpness
        elif (
            (
                subject_tiles >= s.min_subject_tiles
                or (lone_sharp_tile and focus_ratio >= s.min_single_tile_focus_ratio)
            )
            and (cluster_share >= s.min_subject_cluster_share or subject_tiles >= s.confident_subject_tiles)
            and focus_ratio >= s.min_focus_ratio
            and subject_sharpness >= s.min_shallow_subject_sharpness
        ):
            flag, score_basis = "SHALLOW_FOCUS", subject_sharpness
        else:
            # Fewer than `sharp_area_ratio` of the informative tiles are sharp, so this median is
            # below the threshold and the score stays under 0.5 even if a stray tile is sharp.
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
                "sharp_tiles": float(total_sharp),
                **scene,
            },
        )

    def _global_result(self, variance: float, scene: dict[str, float]) -> AnalysisResult:
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
                "sharp_tiles": 0.0,
                **scene,
            },
        )
