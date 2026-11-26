import cv2
import numpy as np
import pytest

from app.schemas import PhotoMetrics
from app.suggest import NOT_SUGGESTED, RULES, suggest_preset
from app.tuning import PRESETS
from tests.conftest import bokeh_image, encode, landscape_image, sharp_image, solid_image


def photo(
    blur_flag: str = "SHARP",
    sharp_area: float = 0.7,
    subject_tiles: float = 6,
    focus_ratio: float = 2.0,
    brightness: float = 120.0,
    highlights: float = 0.0,
    shadows: float = 0.0,
    top_detail_ratio: float = 1.0,
    top_brightness_gain: float = 0.0,
    dark_share: float = 0.0,
    vivid_light: float = 0.0,
    soft_texture_share: float = 0.1,
    **exif: float,
) -> PhotoMetrics:
    exposure = {"average_brightness": brightness, "highlight_ratio": highlights, "shadow_ratio": shadows}
    return PhotoMetrics(
        flags={"blur": blur_flag, "overexposure": "OK", "underexposure": "OK", "scene": "OK"},
        metrics={
            "blur": {
                "sharp_area": sharp_area,
                "subject_tiles": subject_tiles,
                "focus_ratio": focus_ratio,
                "top_detail_ratio": top_detail_ratio,
                "top_brightness_gain": top_brightness_gain,
            },
            "overexposure": exposure,
            "underexposure": exposure,
            "scene": {
                "dark_share": dark_share,
                "vivid_light": vivid_light,
                "soft_texture_share": soft_texture_share,
                **{f"exif_{k}": v for k, v in exif.items()},
            },
        },
    )


NEUTRAL = photo()  # sharp across the frame, mid exposure, no EXIF: matches nothing

# Pixel-only scenes (no EXIF, like the web-sourced test folders).
SCENES = {
    "concert_events": photo(brightness=45, shadows=0.3, dark_share=0.5, vivid_light=0.03),
    "wildlife": photo("BLURRY", sharp_area=0.03, subject_tiles=1, focus_ratio=30),
    "sports_action": photo(soft_texture_share=0.5, top_brightness_gain=-20),
    "night_lowkey": photo(brightness=35, shadows=0.3),
    "high_key": photo(brightness=200, highlights=0.2),
    # smooth bright sky over detail; the blur flag doesn't matter (sky often made it BLURRY)
    "landscape": photo("BLURRY", sharp_area=0.2, top_detail_ratio=0.1, top_brightness_gain=40),
    "portrait_bokeh": photo("SHALLOW_FOCUS", sharp_area=0.15, subject_tiles=12, focus_ratio=25),
}

# Camera originals: EXIF alone is enough (the pixels here match nothing).
EXIF_SCENES = {
    "concert_events": photo(brightness=50, iso=6400),
    "wildlife": photo(focal_length_35mm=500),
    "sports_action": photo(exposure_time=1 / 2000, focal_length_35mm=200),
    "macro": photo(subject_distance=0.15),
    "night_lowkey": photo(brightness=40, exposure_time=8),
    "landscape": photo(f_number=11, focal_length_35mm=24),
    "portrait_bokeh": photo(f_number=1.8, focal_length_35mm=85),
}


@pytest.mark.parametrize("preset_id", list(SCENES))
def test_each_pixel_scene_batch_predicts_its_preset(preset_id):
    batch = [SCENES[preset_id]] * 6 + [NEUTRAL] * 2
    suggestion = suggest_preset(batch)
    assert suggestion is not None
    assert suggestion.preset_id == preset_id
    assert suggestion.matched == 6 and suggestion.total == 8
    assert suggestion.confidence == pytest.approx(0.75)
    assert suggestion.reasons and suggestion.reasons[0].startswith("6 of 8 photos")


@pytest.mark.parametrize("preset_id", list(EXIF_SCENES))
def test_each_exif_scene_batch_predicts_its_preset(preset_id):
    suggestion = suggest_preset([EXIF_SCENES[preset_id]] * 5)
    assert suggestion is not None
    assert suggestion.preset_id == preset_id
    assert any("5 of 5 photos" in r for r in suggestion.reasons)


def test_telephoto_fast_shutter_is_wildlife_not_sports():
    """Birds in flight: fast shutter on a long lens. Wildlife outranks sports, which excludes telephoto."""
    bird_in_flight = photo(exposure_time=1 / 3200, focal_length_35mm=600)
    assert suggest_preset([bird_in_flight] * 4).preset_id == "wildlife"


def test_bright_high_iso_is_not_concert():
    assert suggest_preset([photo(brightness=150, iso=6400)] * 4) is None


def test_priority_beats_larger_share():
    """Concert photos also read as a subject on a soft background; the specific scene must win."""
    concert_with_subject = photo(
        "SHALLOW_FOCUS", sharp_area=0.2, focus_ratio=25, brightness=45, dark_share=0.5, vivid_light=0.03
    )
    batch = [concert_with_subject] * 4 + [SCENES["portrait_bokeh"]] * 4
    suggestion = suggest_preset(batch)
    assert suggestion.preset_id == "concert_events"  # 50%, though portrait matches 100%
    assert ("portrait_bokeh", 1.0) in {(a.preset_id, a.confidence) for a in suggestion.alternatives}


def test_pixel_and_exif_reasons_are_both_reported():
    batch = [SCENES["landscape"]] * 3 + [EXIF_SCENES["landscape"]] * 2
    suggestion = suggest_preset(batch)
    assert suggestion.preset_id == "landscape"
    assert suggestion.matched == 5
    assert len(suggestion.reasons) == 2


@pytest.mark.parametrize(
    ("top_detail_ratio", "top_brightness_gain"),
    [
        pytest.param(0.8, 40, id="detailed-top"),
        pytest.param(0.1, -30, id="dark-smooth-top"),  # e.g. a dark ceiling, not sky
    ],
)
def test_non_sky_tops_are_not_landscape(top_detail_ratio, top_brightness_gain):
    p = photo(top_detail_ratio=top_detail_ratio, top_brightness_gain=top_brightness_gain)
    assert suggest_preset([p] * 6) is None


def test_dark_without_vivid_light_is_night_not_concert():
    assert suggest_preset([photo(brightness=35, shadows=0.3, dark_share=0.6)] * 4).preset_id == "night_lowkey"


def test_neutral_batch_suggests_nothing():
    assert suggest_preset([NEUTRAL] * 10) is None


def test_small_batch_suggests_nothing():
    assert suggest_preset([SCENES["night_lowkey"]] * 2) is None


def test_below_share_threshold_suggests_nothing():
    assert suggest_preset([SCENES["night_lowkey"]] * 3 + [NEUTRAL] * 7) is None  # 30% < 40%


def test_runner_up_is_listed_as_alternative():
    batch = [SCENES["night_lowkey"]] * 5 + [SCENES["portrait_bokeh"]] * 3 + [NEUTRAL] * 2
    suggestion = suggest_preset(batch)
    assert suggestion.preset_id == "night_lowkey"
    assert [(a.preset_id, a.confidence) for a in suggestion.alternatives] == [("portrait_bokeh", 0.3)]


def test_soft_photo_without_clear_subject_is_not_bokeh():
    weak = photo("BLURRY", sharp_area=0.1, subject_tiles=2, focus_ratio=3)
    assert suggest_preset([weak] * 6) is None


def test_photos_with_missing_metrics_are_tolerated():
    batch = [PhotoMetrics()] * 3 + [PhotoMetrics(flags={"blur": "SHARP"})] + [SCENES["night_lowkey"]] * 4
    assert suggest_preset(batch).preset_id == "night_lowkey"


def test_rules_target_existing_presets_except_intent_ones():
    preset_ids = {p.id for p in PRESETS}
    rule_ids = [r.preset_id for r in RULES]
    assert set(rule_ids) <= preset_ids
    assert len(rule_ids) == len(set(rule_ids))
    assert set(rule_ids).isdisjoint(NOT_SUGGESTED)
    assert set(rule_ids) == preset_ids - NOT_SUGGESTED  # every scene preset is suggestable
    assert RULES[-1].preset_id == "portrait_bokeh"  # the generic rule comes last


# --- end to end: real analysis output fed to the endpoint ---------------------------------------------


def concert_image(width: int = 800, height: int = 600) -> np.ndarray:
    """Mostly black frame with saturated colored light spots (stage lighting)."""
    img = np.full((height, width, 3), 8, dtype=np.uint8)
    rng = np.random.default_rng(1)
    for _ in range(40):
        x, y = int(rng.integers(0, width)), int(rng.integers(0, height // 2))
        color = [(255, 40, 200), (40, 80, 255), (30, 255, 120)][int(rng.integers(0, 3))]
        cv2.circle(img, (x, y), int(rng.integers(6, 18)), color, -1)
    return img


def analyze_and_suggest(client, images):
    files = [("files", (f"{i}.png", encode(img, ".png"), "image/png")) for i, img in enumerate(images)]
    results = client.post("/api/v1/cull-batch", files=files).json()["results"]
    photos = [
        {
            "flags": {name: a["flag"] for name, a in r["analyses"].items()},
            "metrics": {name: a["metrics"] for name, a in r["analyses"].items()},
        }
        for r in results
    ]
    res = client.post("/api/v1/suggest-preset", json={"photos": photos})
    assert res.status_code == 200
    return res.json()


@pytest.mark.parametrize(
    ("images", "expected"),
    [
        pytest.param([solid_image(2)] * 4, "night_lowkey", id="near-black"),
        pytest.param([concert_image()] * 4, "concert_events", id="stage-lights"),
        pytest.param([landscape_image(0.6)] * 4, "landscape", id="sky-over-detail"),
        pytest.param([bokeh_image((300, 200, 200, 200))] * 4, "portrait_bokeh", id="medium-subject"),
        pytest.param([bokeh_image((400, 300, 30, 30))] * 4, "wildlife", id="tiny-subject"),
    ],
)
def test_endpoint_predicts_preset_from_real_analysis(client, images, expected):
    assert analyze_and_suggest(client, images)["preset_id"] == expected


def test_endpoint_texture_everywhere_is_not_landscape(client):
    assert analyze_and_suggest(client, [sharp_image()] * 4) is None


def test_endpoint_returns_null_for_small_batch(client):
    assert analyze_and_suggest(client, [solid_image(2)]) is None


def test_endpoint_rejects_oversized_request(client):
    res = client.post("/api/v1/suggest-preset", json={"photos": [{}] * 1001})
    assert res.status_code == 422
