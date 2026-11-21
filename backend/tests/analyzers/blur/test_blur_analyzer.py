import cv2
import numpy as np
import pytest

from app.analyzers.blur import BlurAnalyzer, BlurSettings
from app.analyzers.blur.analyzer import grid_shape, largest_cluster, normalize_score, tile_stats
from app.imaging import PreparedImage
from tests.conftest import blurry_image, bokeh_image, sharp_image, soft_background

THRESHOLD = 80.0
W, H = 800, 600


@pytest.fixture
def analyzer():
    return BlurAnalyzer(BlurSettings(threshold=THRESHOLD))


def analyze(analyzer, img):
    return analyzer.analyze(PreparedImage(img))


# --- whole-image cases -------------------------------------------------------------


def test_sharp_image_is_sharp(analyzer):
    result = analyze(analyzer, sharp_image())
    assert result.flag == "SHARP"
    assert result.score > 0.5


def test_blurry_image_is_flagged(analyzer):
    result = analyze(analyzer, blurry_image())
    assert result.flag == "BLURRY"
    assert result.score < 0.5
    assert result.metrics["laplacian_variance"] < THRESHOLD


def test_out_of_focus_scene_is_blurry(analyzer):
    result = analyze(analyzer, soft_background())
    assert result.flag == "BLURRY"
    assert result.score < 0.5


def test_uniformly_soft_image_is_blurry(analyzer):
    """Mild blur everywhere (e.g. camera shake): no tile reaches the threshold."""
    result = analyze(analyzer, cv2.GaussianBlur(sharp_image(), (0, 0), 3))
    assert result.flag == "BLURRY"
    assert result.metrics["subject_tiles"] == 0


# --- shallow focus: sharp subject, intentionally blurred background ------------------


@pytest.mark.parametrize(
    "box",
    [
        pytest.param((300, 200, 200, 200), id="centered"),
        pytest.param((0, 200, 160, 200), id="left-edge"),
        pytest.param((W - 180, H - 160, 180, 160), id="bottom-right-corner"),
        pytest.param((500, 100, 140, 140), id="small-4pct"),
    ],
)
def test_subject_on_blurred_background_is_shallow_focus(analyzer, box):
    result = analyze(analyzer, bokeh_image(box))
    assert result.flag == "SHALLOW_FOCUS"
    assert result.score > 0.5
    # The old global rule would have flagged most of these; the subject is what's scored.
    assert result.metrics["subject_sharpness"] > result.metrics["laplacian_variance"]
    assert result.metrics["focus_ratio"] >= analyzer.settings.min_focus_ratio


def test_isolated_sharp_speck_on_noisy_background_is_blurry(analyzer):
    """A lone detail smaller than a tile (stray highlight, twig) isn't an in-focus subject unless it
    stands out very strongly (ratio >= `min_single_tile_focus_ratio`); here the rest is noisy."""
    img = bokeh_image((400, 300, 30, 30)).astype(np.float64)
    speck = np.ones(img.shape[:2], bool)
    speck[300:330, 400:430] = False  # leave the speck itself untouched
    noise = np.random.default_rng(3).normal(0, 8, img.shape[:2]) * speck
    result = analyze(analyzer, np.clip(img + noise[..., None], 0, 255).astype(np.uint8))
    assert result.metrics["subject_tiles"] == 1
    assert result.metrics["focus_ratio"] < analyzer.settings.min_single_tile_focus_ratio
    assert result.flag == "BLURRY"
    assert result.score < 0.5


def test_lone_sharp_tile_on_clean_background_is_shallow_focus(analyzer):
    """Small subject, very soft clean rest of the frame: one sharp tile is accepted by design."""
    result = analyze(analyzer, bokeh_image((400, 300, 30, 30)))
    assert result.metrics["subject_tiles"] == 1
    assert result.metrics["focus_ratio"] >= analyzer.settings.min_single_tile_focus_ratio
    assert result.flag == "SHALLOW_FOCUS"


def test_scattered_sharp_tiles_are_not_a_subject(analyzer):
    img = soft_background()
    sharp = sharp_image()
    # Far-apart specks, each inside a single ~67px tile of the 12x9 grid.
    for x, y in [(20, 20), (700, 20), (20, 480), (700, 480)]:
        img[y : y + 25, x : x + 25] = sharp[y : y + 25, x : x + 25]
    result = analyze(analyzer, img)
    assert result.flag == "BLURRY"
    assert result.metrics["subject_tiles"] <= 1


def test_fragmented_sharp_tiles_are_not_shallow_focus(analyzer):
    """A 2-tile cluster plus several far-apart sharp tiles on a soft frame is noise, not a subject."""
    img = soft_background()
    sharp = sharp_image()
    # Tiles are ~67px on the 12x9 grid: one 2-tile cluster and five isolated tiles.
    for x, y, w, h in [
        (267, 200, 133, 67),
        (0, 0, 67, 67),
        (733, 0, 67, 67),
        (0, 533, 67, 67),
        (733, 533, 67, 67),
        (733, 267, 67, 67),
    ]:
        img[y : y + h, x : x + w] = sharp[y : y + h, x : x + w]
    result = analyze(analyzer, img)
    assert result.metrics["subject_tiles"] >= 2
    assert result.flag == "BLURRY"
    assert result.score < 0.5
    # The guard is what rejects it: without it, every other SHALLOW_FOCUS gate passes.
    lenient = BlurAnalyzer(BlurSettings(threshold=THRESHOLD, min_subject_cluster_share=0.0))
    assert analyze(lenient, img).flag == "SHALLOW_FOCUS"


def test_large_fragmented_subject_is_still_shallow_focus(analyzer):
    """A real subject with smooth areas leaves sharp tiles scattered around it; a big cluster still counts."""
    img = soft_background()
    sharp = sharp_image()
    # Tiles are ~67px on the 12x9 grid: one 3x2-tile cluster plus isolated tiles elsewhere.
    for x, y, w, h in [
        (267, 200, 200, 133),
        (0, 0, 67, 67),
        (133, 0, 67, 67),
        (267, 0, 67, 67),
        (667, 0, 67, 67),
        (0, 533, 67, 67),
        (267, 533, 67, 67),
        (667, 533, 67, 67),
        (733, 267, 67, 67),
    ]:
        img[y : y + h, x : x + w] = sharp[y : y + h, x : x + w]
    result = analyze(analyzer, img)
    s = analyzer.settings
    assert result.metrics["subject_tiles"] >= s.confident_subject_tiles
    assert result.metrics["subject_tiles"] / result.metrics["sharp_tiles"] < s.min_subject_cluster_share
    assert result.flag == "SHALLOW_FOCUS"


def test_weak_separation_is_blurry():
    """A subject barely sharper than its background isn't deliberate shallow focus."""
    background = cv2.GaussianBlur(sharp_image(), (0, 0), 3)
    subject = cv2.GaussianBlur(sharp_image(), (0, 0), 2)
    img = background.copy()
    img[200:400, 300:500] = subject[200:400, 300:500]
    result = BlurAnalyzer(BlurSettings(threshold=THRESHOLD)).analyze(PreparedImage(img))
    assert result.metrics["subject_tiles"] >= 2  # there *is* a sharp-enough cluster...
    assert result.metrics["focus_ratio"] < 4.0  # ...but it doesn't stand out
    assert result.flag == "BLURRY"


def test_soft_subject_on_softer_background_is_blurry(analyzer):
    """The subject is far sharper than the background, but not sharp in absolute terms."""
    img = soft_background()
    soft_subject = cv2.GaussianBlur(sharp_image(), (0, 0), 2.6)
    img[200:400, 300:500] = soft_subject[200:400, 300:500]
    result = analyze(analyzer, img)
    assert result.metrics["subject_tiles"] >= 2
    assert result.metrics["focus_ratio"] >= analyzer.settings.min_focus_ratio
    assert THRESHOLD <= result.metrics["subject_sharpness"] < analyzer.settings.min_shallow_subject_sharpness
    assert result.flag == "BLURRY"
    assert result.score < 0.5


def test_moderate_separation_is_blurry(analyzer):
    """A decently sharp region over a background that is soft but not *very* soft (noisy, like a
    shaky shot) is not deliberate shallow focus."""
    rng = np.random.default_rng(3)
    img = soft_background().astype(np.float64)
    img += rng.normal(0, 5.0, img.shape[:2])[..., None]
    img = np.clip(img, 0, 255).astype(np.uint8)
    subject = cv2.GaussianBlur(sharp_image(), (0, 0), 2.2)
    img[200:400, 300:500] = subject[200:400, 300:500]
    result = analyze(analyzer, img)
    assert result.metrics["subject_sharpness"] >= analyzer.settings.min_shallow_subject_sharpness
    assert 4.0 <= result.metrics["focus_ratio"] < analyzer.settings.min_focus_ratio
    assert result.flag == "BLURRY"


def test_sharp_area_just_under_half_is_sharp(analyzer):
    """~42% of the informative tiles sharp is enough for SHARP (the ratio is 0.40)."""
    img = soft_background()
    img[:, : int(W * 0.4)] = sharp_image()[:, : int(W * 0.4)]
    result = analyze(analyzer, img)
    assert 0.4 <= result.metrics["sharp_area"] < 0.5
    assert result.flag == "SHARP"


def test_subject_on_flat_backdrop_is_sharp(analyzer):
    """Plain studio backdrop: flat tiles are ignored, nothing visible is blurred."""
    result = analyze(analyzer, bokeh_image((300, 200, 200, 200), flat=True))
    assert result.flag == "SHARP"


# --- fallbacks ---------------------------------------------------------------------


def test_flat_image_falls_back_to_global_rule(analyzer):
    result = analyze(analyzer, np.full((H, W, 3), 128, dtype=np.uint8))
    assert result.flag == "BLURRY"
    assert result.score == 0.0


@pytest.mark.parametrize(("img", "flag"), [(sharp_image(60, 40), "SHARP"), (blurry_image(60, 40), "BLURRY")])
def test_tiny_image_falls_back_to_global_rule(analyzer, img, flag):
    result = analyze(analyzer, img)
    assert result.flag == flag
    assert result.metrics["subject_tiles"] == 0


def test_metrics_are_finite_floats(analyzer):
    for img in (sharp_image(), blurry_image(), bokeh_image((300, 200, 200, 200), flat=True)):
        metrics = analyze(analyzer, img).metrics
        assert set(metrics) == {
            "laplacian_variance",
            "subject_sharpness",
            "background_sharpness",
            "sharp_area",
            "focus_ratio",
            "subject_tiles",
            "sharp_tiles",
        }
        assert all(isinstance(v, float) and np.isfinite(v) for v in metrics.values())


# --- helpers -----------------------------------------------------------------------


def test_grid_shape_follows_aspect_ratio():
    assert grid_shape(600, 800, 12) == (9, 12)
    assert grid_shape(800, 600, 12) == (16, 12)
    assert grid_shape(40, 60, 12) is None


def test_tile_stats_localizes_sharpness():
    gray = np.full((120, 120), 100, dtype=np.uint8)
    gray[:40, :40] = cv2.cvtColor(sharp_image(40, 40), cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness, contrast = tile_stats(gray, lap, 3, 3)
    assert sharpness.shape == contrast.shape == (3, 3)
    assert sharpness[0, 0] == sharpness.max() > 0
    assert contrast[2, 2] == 0 and sharpness[2, 2] == 0


def test_largest_cluster_picks_biggest_connected_region():
    mask = np.zeros((5, 5), dtype=bool)
    mask[0, 0] = True  # isolated
    mask[2:4, 2:5] = True  # 6-tile block
    mask[4, 1] = True  # diagonal neighbour of (3, 2), joins via 8-connectivity
    cluster = largest_cluster(mask)
    assert cluster.sum() == 7
    assert not cluster[0, 0]


def test_largest_cluster_empty_mask():
    assert not largest_cluster(np.zeros((3, 3), dtype=bool)).any()


@pytest.mark.parametrize(
    ("variance", "expected"),
    [(0.0, 0.0), (80.0, 0.5), (45.2, 0.361), (1e9, 1.0)],
)
def test_normalize_score(variance, expected):
    assert normalize_score(variance, THRESHOLD) == pytest.approx(expected, abs=1e-3)
