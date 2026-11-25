import pytest

from app.schemas import PhotoMetrics
from app.suggest import RULES, suggest_preset
from app.tuning import PRESETS
from tests.conftest import bokeh_image, encode, landscape_image, sharp_image, solid_image


def photo(
    blur_flag: str = "SHARP",
    sharp_area: float = 0.5,
    subject_tiles: float = 6,
    focus_ratio: float = 2.0,
    brightness: float = 120.0,
    highlights: float = 0.0,
    shadows: float = 0.0,
    top_detail_ratio: float = 1.0,
    top_brightness_gain: float = 0.0,
) -> PhotoMetrics:
    exposure = {"average_brightness": brightness, "highlight_ratio": highlights, "shadow_ratio": shadows}
    return PhotoMetrics(
        flags={"blur": blur_flag, "overexposure": "OK", "underexposure": "OK"},
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
        },
    )


NEUTRAL = photo()  # sharp-ish, mid exposure: matches nothing

SCENES = {
    "wildlife": photo("BLURRY", sharp_area=0.03, subject_tiles=1, focus_ratio=30),
    "portrait_bokeh": photo("SHALLOW_FOCUS", sharp_area=0.15, subject_tiles=12, focus_ratio=25),
    "concert_events": photo(brightness=40, highlights=0.03, shadows=0.2),
    "night_lowkey": photo(brightness=35, shadows=0.3),
    "high_key": photo(brightness=200, highlights=0.2),
    # smooth bright sky over detail; the blur flag doesn't matter (sky often made it BLURRY)
    "landscape": photo("BLURRY", sharp_area=0.2, top_detail_ratio=0.1, top_brightness_gain=40),
}


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


@pytest.mark.parametrize("preset_id", list(SCENES))
def test_each_scene_batch_predicts_its_preset(preset_id):
    batch = [SCENES[preset_id]] * 6 + [NEUTRAL] * 2
    suggestion = suggest_preset(batch)
    assert suggestion is not None
    assert suggestion.preset_id == preset_id
    assert suggestion.matched == 6 and suggestion.total == 8
    assert suggestion.confidence == pytest.approx(0.75)
    assert suggestion.reasons and suggestion.reasons[0].startswith("6 of 8 photos")


def test_neutral_batch_suggests_nothing():
    assert suggest_preset([NEUTRAL] * 10) is None


def test_small_batch_suggests_nothing():
    assert suggest_preset([SCENES["night_lowkey"]] * 2) is None


def test_below_share_threshold_suggests_nothing():
    assert suggest_preset([SCENES["night_lowkey"]] * 3 + [NEUTRAL] * 7) is None  # 30% < 40%


def test_tie_prefers_the_more_specific_scene():
    batch = [SCENES["wildlife"]] * 4 + [SCENES["landscape"]] * 4
    assert suggest_preset(batch).preset_id == "wildlife"


def test_runner_up_is_listed_as_alternative():
    batch = [SCENES["night_lowkey"]] * 5 + [SCENES["portrait_bokeh"]] * 3 + [NEUTRAL] * 2
    suggestion = suggest_preset(batch)
    assert suggestion.preset_id == "night_lowkey"
    assert [(a.preset_id, a.confidence) for a in suggestion.alternatives] == [("portrait_bokeh", 0.3)]


def test_dark_bokeh_photo_can_count_for_two_scenes():
    dark_bokeh = photo(
        "SHALLOW_FOCUS", sharp_area=0.2, subject_tiles=8, focus_ratio=30, brightness=40, shadows=0.2
    )
    suggestion = suggest_preset([dark_bokeh] * 5)
    assert suggestion.preset_id == "portrait_bokeh"  # priority over night on a tie
    assert "night_lowkey" in {a.preset_id for a in suggestion.alternatives}


def test_soft_photo_without_clear_subject_is_not_bokeh():
    weak = photo("BLURRY", sharp_area=0.1, subject_tiles=2, focus_ratio=3)
    assert suggest_preset([weak] * 6) is None


def test_photos_with_missing_metrics_are_tolerated():
    batch = [PhotoMetrics()] * 3 + [PhotoMetrics(flags={"blur": "SHARP"})] + [SCENES["night_lowkey"]] * 4
    assert suggest_preset(batch).preset_id == "night_lowkey"


def test_rules_only_target_existing_scene_presets():
    preset_ids = {p.id for p in PRESETS}
    rule_ids = [r.preset_id for r in RULES]
    assert set(rule_ids) <= preset_ids
    assert len(rule_ids) == len(set(rule_ids))
    assert set(rule_ids).isdisjoint({"default", "strict_cull", "lenient_cull", "sports_action", "macro"})


# --- end to end: real analysis output fed to the endpoint ---------------------------------------------


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
        # 60% sky: the detailed band is large enough to be SHARP. An extreme 80% sky also reads as a
        # small subject on a soft background, and portrait wins that tie by priority.
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
