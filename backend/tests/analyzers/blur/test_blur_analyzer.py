import cv2
import numpy as np
import pytest

from app.analyzers.blur import BlurAnalyzer, BlurSettings
from app.analyzers.blur.analyzer import (
    grid_shape,
    largest_cluster,
    normalize_score,
    reblur_sharpness,
    tile_stats,
)
from app.imaging import Face, PreparedImage
from tests.conftest import blurry_image, bokeh_image, landscape_image, sharp_image, soft_background

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
    for img in (
        sharp_image(),
        blurry_image(),
        bokeh_image((300, 200, 200, 200), flat=True),
        sharp_image(60, 40),
    ):
        metrics = analyze(analyzer, img).metrics
        assert set(metrics) == {
            "laplacian_variance",
            "subject_sharpness",
            "background_sharpness",
            "sharp_area",
            "focus_ratio",
            "subject_tiles",
            "sharp_tiles",
            "top_detail_ratio",
            "top_brightness_gain",
            "reblur_sharpness",
            "edge_coverage",
            "noise_level",
        }
        assert all(isinstance(v, float) and np.isfinite(v) for v in metrics.values())


# --- landscapes: smooth sky over a sharp scene ----------------------------------------


SHARP_REGION = {"min_tile_contrast": 10, "min_sharp_region_area": 0.05, "min_sharp_region_sharpness": 130}


def test_smooth_sky_dilutes_sharp_area_by_default(analyzer):
    """The bug the sharp-region rule fixes: textureless sky counts as 'not sharp'."""
    result = analyze(analyzer, landscape_image())
    assert result.metrics["sharp_area"] < 0.4
    assert result.flag != "SHARP"


def test_sharp_region_rule_labels_landscape_sharp():
    analyzer = BlurAnalyzer(BlurSettings(threshold=THRESHOLD, **SHARP_REGION))
    result = analyze(analyzer, landscape_image())
    assert result.flag == "SHARP"
    assert result.score > 0.5


def test_sharp_region_rule_is_off_by_default():
    assert BlurSettings().min_sharp_region_area == 1.0


@pytest.mark.parametrize(
    "img",
    [
        pytest.param(cv2.GaussianBlur(sharp_image(), (0, 0), 3), id="uniformly-soft"),
        pytest.param(soft_background(), id="out-of-focus-scene"),
        pytest.param(cv2.GaussianBlur(landscape_image(), (0, 0), 3), id="blurred-landscape"),
    ],
)
def test_sharp_region_rule_still_flags_blurry_photos(img):
    analyzer = BlurAnalyzer(BlurSettings(threshold=THRESHOLD, **SHARP_REGION))
    assert analyze(analyzer, img).flag == "BLURRY"


# --- re-blur rescue: crisp edges, little texture -------------------------------------


def smooth_crisp_scene() -> np.ndarray:
    """Smooth hills and sky with crisp outlines but almost no fine texture, the kind of real photo the
    tile analysis called BLURRY (smooth landscapes, dunes, heavy JPEG)."""
    yy, xx = np.indices((H, W), dtype=np.float64)
    img = 150 + 0.06 * yy  # sky gradient
    for i, (amp, period, base, shade) in enumerate(
        [(60, 230, 330, 95), (40, 160, 420, 70), (30, 120, 500, 45)]
    ):
        ridge = base + amp * np.sin(xx / period + i)
        img = np.where(yy > ridge, shade + 0.02 * (yy - ridge), img)  # crisp ridge line, smooth fill
    return cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)


def test_reblur_sharpness_orders_by_blur():
    # (Not on the 8 px checkerboard: a periodic pattern near the 9 px re-blur length misleads it.)
    gray = cv2.cvtColor(smooth_crisp_scene(), cv2.COLOR_BGR2GRAY)
    blurred = [gray] + [cv2.GaussianBlur(gray, (0, 0), s) for s in (1.5, 3)]
    values = [reblur_sharpness(g) for g in blurred]
    assert values[0] > values[1] > values[2]


def test_reblur_sharpness_ignores_noise_without_edges():
    """Faint noise on soft shapes is pixel-level 'crisp' but not an edge: no edges -> 0."""
    assert reblur_sharpness(cv2.cvtColor(soft_background(), cv2.COLOR_BGR2GRAY)) == 0.0


def test_smooth_scene_with_crisp_edges_is_rescued(analyzer):
    img = smooth_crisp_scene()
    tiles_only = BlurAnalyzer(BlurSettings(threshold=THRESHOLD, min_reblur_sharpness=0))
    assert analyze(tiles_only, img).flag == "BLURRY"  # the bug: little texture reads as blurry
    result = analyze(analyzer, img)
    assert result.flag == "SHARP"
    assert result.score > 0.5
    assert result.metrics["reblur_sharpness"] >= analyzer.settings.min_reblur_sharpness


@pytest.mark.parametrize("sigma", [2.5, 4.0])
def test_blurred_smooth_scene_stays_blurry(analyzer, sigma):
    result = analyze(analyzer, cv2.GaussianBlur(smooth_crisp_scene(), (0, 0), sigma))
    assert result.flag == "BLURRY"
    assert result.score < 0.5


def test_rescue_skipped_on_very_noisy_image(analyzer):
    img = smooth_crisp_scene().astype(np.float64)
    noise = np.random.default_rng(0).normal(0, 9, img.shape[:2])[..., None]
    noisy = np.clip(cv2.GaussianBlur(img, (0, 0), 3) + noise, 0, 255).astype(np.uint8)
    result = analyze(analyzer, noisy)
    assert result.metrics["noise_level"] > 5
    assert result.flag == "BLURRY"


def test_rescue_can_be_disabled():
    analyzer = BlurAnalyzer(BlurSettings(threshold=THRESHOLD, min_reblur_sharpness=0))
    assert analyze(analyzer, smooth_crisp_scene()).flag == "BLURRY"


def test_scene_metrics_detect_open_sky(analyzer):
    sky = analyze(analyzer, landscape_image()).metrics
    assert sky["top_detail_ratio"] < 0.5 and sky["top_brightness_gain"] > 0
    texture = analyze(analyzer, sharp_image()).metrics
    assert texture["top_detail_ratio"] > 0.5


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


# --- face override (Portrait preset) -----------------------------------------------


def with_face(img, box):
    """PreparedImage whose detected faces are fixed (the cached property is pre-filled), so the
    override logic is tested without depending on the face model recognising synthetic pixels."""
    image = PreparedImage(img)
    image.__dict__["faces"] = [Face(*box, score=0.9)] if box else []
    return image


FACE_BOX = (300, 200, 200, 200)  # matches the sharp patch in bokeh_image((300, 200, 200, 200))


def test_face_override_is_off_by_default(analyzer):
    image = with_face(soft_background(), FACE_BOX)
    assert analyzer.analyze(image).flag == "BLURRY"
    assert "face_sharpness" not in analyzer.analyze(image).metrics


def test_sharp_face_turns_blurry_into_shallow_focus():
    # A sharp face on a frame that's otherwise soft at tile level (smooth skin, bokeh) is a portrait.
    img = soft_background()
    img[200:400, 300:500] = sharp_image(200, 200)
    analyzer = BlurAnalyzer(BlurSettings(threshold=1e6, min_reblur_sharpness=0, face_sharpness=10))
    result = analyzer.analyze(with_face(img, FACE_BOX))
    assert result.flag == "SHALLOW_FOCUS"
    assert result.metrics["face_sharpness"] >= 10
    assert result.score >= 0.5


def test_soft_face_makes_sharp_frame_blurry():
    # Everything around the face is sharp (e.g. crisp bokeh edges, background in focus), but the face isn't.
    img = sharp_image()
    img[200:400, 300:500] = soft_background(200, 200)
    analyzer = BlurAnalyzer(BlurSettings(face_sharpness=10))
    assert analyzer.analyze(PreparedImage(img)).flag == "SHARP"  # sanity check: no face given yet
    result = analyzer.analyze(with_face(img, FACE_BOX))
    assert result.flag == "BLURRY"
    assert result.score < 0.5


def test_no_face_or_tiny_face_keeps_tile_verdict():
    analyzer = BlurAnalyzer(BlurSettings(face_sharpness=10))
    img = bokeh_image((300, 200, 200, 200))
    expected = BlurAnalyzer().analyze(PreparedImage(img)).flag
    assert analyzer.analyze(with_face(img, None)).flag == expected
    tiny = (10, 10, 20, 20)  # under MIN_FACE_WIDTH of an 800 px frame: a background person / false hit
    assert analyzer.analyze(with_face(img, tiny)).flag == expected
