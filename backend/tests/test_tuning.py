import json

import pytest

from app.analyzers.blur import BlurAnalyzer
from app.analyzers.blur.settings import BlurSettings
from app.analyzers.overexposure.settings import OverexposureSettings
from app.analyzers.registry import build_analyzers
from app.analyzers.underexposure.settings import UnderexposureSettings
from app.tuning import PARAMS, PRESETS, SLIDERS, InvalidTuningError, validate_overrides
from tests.conftest import encode, split_image

DEFAULT_SETTINGS = {
    "blur": BlurSettings(),
    "overexposure": OverexposureSettings(),
    "underexposure": UnderexposureSettings(),
}


def post(client, tuning=None, img=None):
    img = split_image(0.8) if img is None else img
    data = {"tuning": tuning if isinstance(tuning, str) else json.dumps(tuning)} if tuning is not None else {}
    return client.post(
        "/api/v1/cull-batch", files=[("files", ("a.png", encode(img, ".png"), "image/png"))], data=data
    )


def test_catalog_lists_params_with_live_defaults(client):
    body = client.get("/api/v1/settings").json()
    assert set(body["params"]) == {"blur", "overexposure", "underexposure"}
    for name, specs in body["params"].items():
        for spec in specs:
            assert spec["default"] == getattr(DEFAULT_SETTINGS[name], spec["key"])
            assert spec["min"] <= spec["default"] <= spec["max"]
    assert body["default_preset"] == "default"


def test_locked_params_are_not_exposed(client):
    keys = {s["key"] for specs in client.get("/api/v1/settings").json()["params"].values() for s in specs}
    assert keys.isdisjoint({"denoise", "proxy_max_width", "max_workers", "max_file_bytes"})


def test_default_slider_levels_reproduce_shipped_defaults():
    for slider in SLIDERS:
        for name, values in slider.levels[slider.default_level].values.items():
            for key, value in values.items():
                assert value == getattr(DEFAULT_SETTINGS[name], key), f"{slider.id}.{name}.{key}"


def test_every_slider_value_is_tunable_and_valid():
    analyzers = build_analyzers()
    for slider in SLIDERS:
        for level in slider.levels:
            validate_overrides(level.values, analyzers)  # bounds and consistency


def test_presets_reference_real_sliders_and_levels():
    sliders = {s.id: s for s in SLIDERS}
    assert PRESETS[0].id == "default"
    for preset in PRESETS:
        assert set(preset.levels) == set(sliders)
        for sid, idx in preset.levels.items():
            assert 0 <= idx < len(sliders[sid].levels)
    assert all(idx == sliders[sid].default_level for sid, idx in PRESETS[0].levels.items())


def test_presets_resolve_to_distinct_slider_levels():
    """The frontend highlights the first preset matching the current values, so none may be identical."""
    combos = [tuple(sorted(p.levels.items())) for p in PRESETS]
    assert len(set(combos)) == len(combos)
    assert len({p.id for p in PRESETS}) == len(PRESETS)


def test_params_cover_only_existing_settings_fields():
    for name, specs in PARAMS.items():
        for spec in specs:
            assert spec.key in type(DEFAULT_SETTINGS[name]).model_fields


def test_override_changes_result_for_one_request_only(client):
    assert post(client).json()["results"][0]["analyses"]["overexposure"]["flag"] == "OVEREXPOSED"
    tuned = post(client, {"overexposure": {"brightness_threshold": 230}}).json()
    assert tuned["results"][0]["analyses"]["overexposure"]["flag"] == "OK"
    # shared startup analyzers are untouched, so the next untuned request is back to default
    assert post(client).json()["results"][0]["analyses"]["overexposure"]["flag"] == "OVEREXPOSED"


@pytest.mark.parametrize(
    "tuning",
    [
        {"blur": {"denoise": False}},  # locked
        {"blur": {"nope": 1}},  # unknown param
        {"nothing": {"threshold": 1}},  # unknown analyzer
        {"blur": {"grid_cols": 500}},  # above bound
        {"blur": {"grid_cols": 12.5}},  # non-integer
        {"blur": {"threshold": "80"}},  # wrong type
        {"blur": {"threshold": True}},  # bool is not a number
        {"blur": {"threshold": 250}},  # above min_shallow_subject_sharpness
        {"blur": {"min_subject_tiles": 20}},  # above confident_subject_tiles
        {"blur": {"min_sharp_region_sharpness": 60}},  # below threshold
        [1, 2],  # not an object
    ],
)
def test_invalid_tuning_is_rejected_with_422(client, tuning):
    assert post(client, tuning).status_code == 422


def test_malformed_json_is_rejected(client):
    assert post(client, "{not json").status_code == 422


def test_validate_overrides_accepts_integral_float_for_int_param():
    out = validate_overrides({"blur": {"grid_cols": 18.0}}, build_analyzers())
    assert out == {"blur": {"grid_cols": 18}}


def test_with_overrides_returns_new_instance_and_keeps_original():
    original = BlurAnalyzer()
    tuned = original.with_overrides({"grid_cols": 20})
    assert tuned is not original
    assert tuned.settings.grid_cols == 20 and original.settings.grid_cols == BlurSettings().grid_cols
    assert original.with_overrides({}) is original


def test_invalid_override_raises_via_apply():
    with pytest.raises(InvalidTuningError):
        validate_overrides({"blur": {"grid_cols": 1}}, build_analyzers())
