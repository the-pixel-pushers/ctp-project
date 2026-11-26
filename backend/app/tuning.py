"""User-tunable analyzer settings: which parameters are editable (and within what bounds), the
plain-language sliders and scene presets built on top of them, and per-request validation.

Anything not listed in `PARAMS` is locked: shared limits in `app/config.py` (proxy width, workers,
upload limits, CORS) and algorithm internals (`MIN_TILE_PX`, `BACKGROUND_FLOOR`, the Gaussian
kernel, connectivity, and the blur `denoise` switch, which rescales every variance value).

The backend is the single source of truth. The frontend fetches `GET /api/v1/settings`, resolves
sliders and presets into raw overrides, and sends them back as the `tuning` form field.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.analyzers.base import Analyzer


class ParamSpec(BaseModel):
    key: str
    label: str
    description: str
    kind: Literal["int", "float"]
    min: float
    max: float
    step: float
    default: float | None = None  # filled from the live analyzer settings in `build_catalog`


class SliderLevel(BaseModel):
    label: str
    values: dict[str, dict[str, float]]  # analyzer -> param -> value


class SliderSpec(BaseModel):
    id: str
    label: str
    description: str
    default_level: int
    levels: list[SliderLevel]


class PresetSpec(BaseModel):
    id: str
    label: str
    description: str
    levels: dict[str, int]  # slider id -> level index


class Catalog(BaseModel):
    params: dict[str, list[ParamSpec]]
    sliders: list[SliderSpec]
    presets: list[PresetSpec]
    default_preset: str


def _p(key: str, label: str, description: str, kind: str, lo: float, hi: float, step: float) -> ParamSpec:
    return ParamSpec(key=key, label=label, description=description, kind=kind, min=lo, max=hi, step=step)


PARAMS: dict[str, list[ParamSpec]] = {
    "blur": [
        _p(
            "threshold",
            "Sharpness cutoff",
            "Laplacian variance at which a tile counts as sharp.",
            "float",
            20,
            300,
            5,
        ),
        _p(
            "grid_cols",
            "Grid columns",
            "Tiles across the frame. More columns find smaller subjects (slower).",
            "int",
            6,
            32,
            1,
        ),
        _p(
            "min_tile_contrast",
            "Min tile contrast",
            "Tiles flatter than this (sky, plain wall) are ignored.",
            "float",
            0,
            30,
            0.5,
        ),
        _p(
            "sharp_area_ratio",
            "Sharp area for SHARP",
            "Share of informative tiles that must be sharp for SHARP.",
            "float",
            0.05,
            0.95,
            0.05,
        ),
        _p(
            "min_subject_tiles",
            "Min subject tiles",
            "Smallest sharp cluster that counts as a subject.",
            "int",
            1,
            30,
            1,
        ),
        _p(
            "min_single_tile_focus_ratio",
            "Lone-tile focus ratio",
            "A single sharp tile counts as the subject above this focus ratio.",
            "float",
            5,
            200,
            1,
        ),
        _p(
            "min_subject_cluster_share",
            "Subject cluster share",
            "Largest cluster's share of all sharp tiles (rejects scattered specks).",
            "float",
            0.1,
            1.0,
            0.05,
        ),
        _p(
            "confident_subject_tiles",
            "Confident subject tiles",
            "A cluster this large skips the cluster-share rule.",
            "int",
            2,
            60,
            1,
        ),
        _p(
            "min_focus_ratio",
            "Min focus ratio",
            "Subject must be this many times sharper than the background for SHALLOW_FOCUS.",
            "float",
            2,
            100,
            1,
        ),
        _p(
            "min_shallow_subject_sharpness",
            "Min subject sharpness",
            "Absolute sharpness the SHALLOW_FOCUS subject must reach.",
            "float",
            20,
            400,
            5,
        ),
        _p(
            "min_sharp_region_area",
            "Sharp region area",
            "A sharp cluster covering this share of informative tiles makes the photo SHARP (1 = off).",
            "float",
            0.01,
            1.0,
            0.01,
        ),
        _p(
            "min_sharp_region_sharpness",
            "Sharp region sharpness",
            "Mean sharpness the cluster needs for the sharp-region rule.",
            "float",
            20,
            400,
            5,
        ),
        _p(
            "min_reblur_sharpness",
            "Edge crispness rescue",
            "A BLURRY photo whose edges stay this crisp (0-1) is SHARP after all (0 = off).",
            "float",
            0.0,
            0.9,
            0.01,
        ),
        _p(
            "face_sharpness",
            "Face sharpness",
            "When a face is found, it must be at least this sharp (Laplacian variance); 0 = off.",
            "float",
            0.0,
            60.0,
            0.5,
        ),
    ],
    "overexposure": [
        _p(
            "brightness_threshold",
            "Brightness cutoff",
            "Mean luma above which a photo is bright overall.",
            "float",
            100,
            230,
            5,
        ),
        _p(
            "highlight_level",
            "Highlight level",
            "Luma at or above which a pixel is a blown highlight.",
            "int",
            200,
            255,
            1,
        ),
        _p(
            "highlight_ratio",
            "Highlight share",
            "Share of blown pixels above which a bright photo is OVEREXPOSED.",
            "float",
            0.005,
            0.5,
            0.005,
        ),
    ],
    "underexposure": [
        _p(
            "brightness_threshold",
            "Darkness cutoff",
            "Mean luma below which a photo is dark overall.",
            "float",
            20,
            140,
            5,
        ),
        _p(
            "shadow_level",
            "Shadow level",
            "Luma at or below which a pixel is a crushed shadow.",
            "int",
            0,
            40,
            1,
        ),
        _p(
            "shadow_ratio",
            "Shadow share",
            "Share of crushed pixels above which a dark photo is UNDEREXPOSED.",
            "float",
            0.005,
            0.5,
            0.005,
        ),
    ],
}


def _level(label: str, **per_analyzer: dict[str, float]) -> SliderLevel:
    return SliderLevel(label=label, values=per_analyzer)


# Each slider's `default_level` must reproduce the shipped defaults (a test checks this). Most have
# five levels with the default in the middle; on/off-style sliders start at level 0.
# Tile-count params scale roughly with grid_cols**2 so "subject size" stays coherent.
SLIDERS: list[SliderSpec] = [
    SliderSpec(
        id="sharpness_strictness",
        label="Sharpness strictness",
        description="How much detail and how crisp the edges must be to count as sharp.",
        default_level=2,
        # min_reblur_sharpness: stricter levels rescue fewer smooth photos but catch more camera shake
        # (noisy calibration set: 0.55 caught ~69% of 7 px shake and kept 97.5% of good photos;
        # 0.61 caught ~83% and kept 94.7%).
        levels=[
            _level(
                "Very lenient",
                blur={"threshold": 50, "min_shallow_subject_sharpness": 70, "min_reblur_sharpness": 0.50},
            ),
            _level(
                "Lenient",
                blur={"threshold": 65, "min_shallow_subject_sharpness": 85, "min_reblur_sharpness": 0.53},
            ),
            _level(
                "Default",
                blur={"threshold": 80, "min_shallow_subject_sharpness": 100, "min_reblur_sharpness": 0.56},
            ),
            _level(
                "Strict",
                blur={"threshold": 100, "min_shallow_subject_sharpness": 125, "min_reblur_sharpness": 0.60},
            ),
            _level(
                "Very strict",
                blur={"threshold": 130, "min_shallow_subject_sharpness": 160, "min_reblur_sharpness": 0.64},
            ),
        ],
    ),
    SliderSpec(
        id="sharp_area",
        label="Sharp area for SHARP",
        description="How much of the frame must be in focus to call the photo fully sharp.",
        default_level=2,
        levels=[
            _level("20%", blur={"sharp_area_ratio": 0.20}),
            _level("30%", blur={"sharp_area_ratio": 0.30}),
            _level("40%", blur={"sharp_area_ratio": 0.40}),
            _level("50%", blur={"sharp_area_ratio": 0.50}),
            _level("60%", blur={"sharp_area_ratio": 0.60}),
        ],
    ),
    SliderSpec(
        id="subject_size",
        label="Subject size",
        description="Expected size of the in-focus subject. Smaller subjects need a finer grid.",
        default_level=2,
        levels=[
            _level("Very large", blur={"grid_cols": 8, "min_subject_tiles": 2, "confident_subject_tiles": 3}),
            _level("Large", blur={"grid_cols": 10, "min_subject_tiles": 2, "confident_subject_tiles": 4}),
            _level("Medium", blur={"grid_cols": 12, "min_subject_tiles": 2, "confident_subject_tiles": 5}),
            _level("Small", blur={"grid_cols": 18, "min_subject_tiles": 3, "confident_subject_tiles": 11}),
            _level("Tiny", blur={"grid_cols": 24, "min_subject_tiles": 4, "confident_subject_tiles": 20}),
        ],
    ),
    SliderSpec(
        id="background_separation",
        label="Background separation",
        description="How much softer the background must be than the subject to call it shallow focus.",
        default_level=2,
        levels=[
            _level("Very low", blur={"min_focus_ratio": 8}),
            _level("Low", blur={"min_focus_ratio": 12}),
            _level("Default", blur={"min_focus_ratio": 20}),
            _level("High", blur={"min_focus_ratio": 30}),
            _level("Very high", blur={"min_focus_ratio": 45}),
        ],
    ),
    SliderSpec(
        id="highlight_tolerance",
        label="Highlight tolerance",
        description="How much blown-out brightness is acceptable before OVEREXPOSED.",
        default_level=2,
        levels=[
            _level("Very strict", overexposure={"brightness_threshold": 140, "highlight_ratio": 0.02}),
            _level("Strict", overexposure={"brightness_threshold": 150, "highlight_ratio": 0.04}),
            _level("Default", overexposure={"brightness_threshold": 160, "highlight_ratio": 0.06}),
            _level("Tolerant", overexposure={"brightness_threshold": 170, "highlight_ratio": 0.10}),
            _level("Very tolerant", overexposure={"brightness_threshold": 180, "highlight_ratio": 0.15}),
        ],
    ),
    SliderSpec(
        id="shadow_tolerance",
        label="Shadow tolerance",
        description="How much crushed darkness is acceptable before UNDEREXPOSED.",
        default_level=2,
        levels=[
            _level("Very strict", underexposure={"brightness_threshold": 100, "shadow_ratio": 0.02}),
            _level("Strict", underexposure={"brightness_threshold": 90, "shadow_ratio": 0.04}),
            _level("Default", underexposure={"brightness_threshold": 80, "shadow_ratio": 0.06}),
            _level("Tolerant", underexposure={"brightness_threshold": 70, "shadow_ratio": 0.10}),
            _level("Very tolerant", underexposure={"brightness_threshold": 60, "shadow_ratio": 0.15}),
        ],
    ),
    # Calibrated on 4,319 real landscape photos (see the "Blur analyzer" notes in backend/CLAUDE.md):
    # "Ignore" kept 82.5% of good originals as non-BLURRY (Default: 70.1%) while still catching
    # ~97% of mild defocus and 70% of camera shake (Default: 81%).
    SliderSpec(
        id="smooth_areas",
        label="Sky & smooth areas",
        description=(
            "Large textureless areas (sky, calm water, snow, sand) can make a sharp photo read as "
            "blurry. Ignore them to judge only the detailed parts."
        ),
        default_level=0,
        levels=[
            _level(
                "Count them",
                blur={
                    "min_tile_contrast": 6,
                    "min_sharp_region_area": 1.0,
                    "min_sharp_region_sharpness": 130,
                },
            ),
            _level(
                "Partly ignore",
                blur={
                    "min_tile_contrast": 8,
                    "min_sharp_region_area": 0.10,
                    "min_sharp_region_sharpness": 140,
                },
            ),
            _level(
                "Ignore",
                blur={
                    "min_tile_contrast": 10,
                    "min_sharp_region_area": 0.05,
                    "min_sharp_region_sharpness": 130,
                },
            ),
        ],
    ),
    # Calibrated on 67 hand-labeled bokeh/portrait photos (Test_photos/bokeh): sharp faces read
    # 11.8-150, missed-focus faces 1.5-8.8 with one at 12.1. At 10, Portrait errors fell from 13 to 6;
    # five of those have no detectable face, one soft face reads 12.1. Photos without a face are judged exactly as before.
    SliderSpec(
        id="face_focus",
        label="Face focus",
        description="In portraits, judge sharpness on the detected face instead of the sharpest area.",
        default_level=0,
        levels=[
            _level("Off", blur={"face_sharpness": 0}),
            _level("Lenient", blur={"face_sharpness": 8}),
            _level("On", blur={"face_sharpness": 10}),
            _level("Strict", blur={"face_sharpness": 13}),
        ],
    ),
]

_DEFAULT_LEVELS = {s.id: s.default_level for s in SLIDERS}


def _preset(id: str, label: str, description: str, **levels: int) -> PresetSpec:
    return PresetSpec(id=id, label=label, description=description, levels={**_DEFAULT_LEVELS, **levels})


PRESETS: list[PresetSpec] = [
    _preset("default", "Default", "Balanced settings for general photos."),
    _preset(
        "strict_cull",
        "Strict cull",
        "Keep only the best: tighter sharpness, subject separation and exposure limits.",
        sharpness_strictness=3,
        sharp_area=3,
        background_separation=3,
        highlight_tolerance=1,
        shadow_tolerance=1,
    ),
    _preset(
        "lenient_cull",
        "Lenient cull",
        "Flag only clearly bad shots: looser sharpness, subject separation and exposure limits.",
        sharpness_strictness=1,
        sharp_area=1,
        background_separation=1,
        highlight_tolerance=3,
        shadow_tolerance=3,
    ),
    _preset(
        "portrait_bokeh",
        "Portrait / bokeh",
        "Subject on a soft background: judged on the face when one is found, else a finer tile grid.",
        subject_size=3,
        face_focus=2,
        # Default separation (20x), not High (30x): on 28 hand-labeled bokeh photos, 30x rejected a
        # sharp portrait at 20.8x while no blurry photo got through at 20x (closest: 17.2x).
        sharp_area=3,
    ),
    _preset(
        "wildlife",
        "Wildlife / telephoto",
        "Tiny subject on a heavily blurred background; lenient sharpness for atmospheric haze.",
        subject_size=4,
        background_separation=3,
        sharp_area=3,
        sharpness_strictness=1,
    ),
    _preset(
        "sports_action",
        "Sports / action",
        "Small, fast subjects; panning leaves backgrounds only partly soft, so separation is relaxed.",
        subject_size=3,
        sharpness_strictness=1,
        background_separation=1,
        sharp_area=1,
    ),
    _preset(
        "landscape",
        "Landscape",
        "Judge only the detailed parts; sky, water and snow no longer count against sharpness.",
        smooth_areas=2,
    ),
    _preset(
        "macro",
        "Macro",
        "Thin depth of field and soft detail: lenient sharpness, large subject.",
        subject_size=1,
        sharpness_strictness=1,
        sharp_area=1,
    ),
    _preset(
        "night_lowkey",
        "Night / low-key",
        "Dark scenes are intentional; noise makes sharpness lenient.",
        sharpness_strictness=1,
        shadow_tolerance=4,
    ),
    _preset("high_key", "High-key", "Bright, airy scenes are intentional.", highlight_tolerance=4),
    _preset(
        "concert_events",
        "Concert / events",
        "Dim venues with stage lights: very lenient sharpness, tolerant shadows and highlights.",
        sharpness_strictness=0,
        shadow_tolerance=4,
        highlight_tolerance=3,
        subject_size=3,
    ),
]


class InvalidTuningError(ValueError):
    """Raised when the `tuning` payload is malformed, out of bounds or inconsistent."""


def build_catalog(analyzers: Sequence[Analyzer]) -> Catalog:
    """The tunable surface, with defaults taken from the live analyzer settings (env included)."""
    by_name = {a.name: a for a in analyzers}
    params: dict[str, list[ParamSpec]] = {}
    for name, specs in PARAMS.items():
        analyzer = by_name.get(name)
        if analyzer is None:
            continue
        params[name] = [
            spec.model_copy(update={"default": getattr(analyzer.settings, spec.key)}) for spec in specs
        ]
    return Catalog(params=params, sliders=SLIDERS, presets=PRESETS, default_preset="default")


def validate_overrides(raw: Any, analyzers: Sequence[Analyzer]) -> dict[str, dict[str, float]]:
    """Check `{analyzer: {param: value}}` against `PARAMS` bounds and cross-parameter rules.
    Unknown analyzers, locked or unknown params, wrong types and out-of-range values are rejected."""
    if not isinstance(raw, Mapping):
        raise InvalidTuningError("`tuning` must be a JSON object of {analyzer: {param: value}}")
    by_name = {a.name: a for a in analyzers}
    clean: dict[str, dict[str, float]] = {}
    for name, values in raw.items():
        specs = {s.key: s for s in PARAMS.get(name, [])}
        if name not in by_name or not specs:
            raise InvalidTuningError(f"Unknown analyzer '{name}'")
        if not isinstance(values, Mapping):
            raise InvalidTuningError(f"Settings for '{name}' must be an object")
        out: dict[str, float] = {}
        for key, value in values.items():
            spec = specs.get(key)
            if spec is None:
                raise InvalidTuningError(f"'{name}.{key}' is not tunable")
            out[key] = _coerce(name, spec, value)
        if out:
            clean[name] = out
    _check_consistency(clean, by_name)
    return clean


def _coerce(analyzer: str, spec: ParamSpec, value: Any) -> float:
    where = f"{analyzer}.{spec.key}"
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidTuningError(f"'{where}' must be a number")
    if spec.kind == "int":
        if value != int(value):
            raise InvalidTuningError(f"'{where}' must be a whole number")
        value = int(value)
    if not spec.min <= value <= spec.max:
        raise InvalidTuningError(f"'{where}' must be between {spec.min:g} and {spec.max:g}")
    return value


def _check_consistency(overrides: dict[str, dict[str, float]], by_name: Mapping[str, Analyzer]) -> None:
    blur = by_name.get("blur")
    if blur is None or "blur" not in overrides:
        return
    s = {**blur.settings.model_dump(), **overrides["blur"]}
    if s["min_shallow_subject_sharpness"] < s["threshold"]:
        raise InvalidTuningError("'blur.min_shallow_subject_sharpness' must be at least 'blur.threshold'")
    if s["confident_subject_tiles"] < s["min_subject_tiles"]:
        raise InvalidTuningError("'blur.confident_subject_tiles' must be at least 'blur.min_subject_tiles'")
    if s["min_sharp_region_sharpness"] < s["threshold"]:
        raise InvalidTuningError("'blur.min_sharp_region_sharpness' must be at least 'blur.threshold'")


def apply_overrides(
    analyzers: Sequence[Analyzer], overrides: Mapping[str, Mapping[str, float]]
) -> list[Analyzer]:
    """Per-request analyzer list; the shared startup instances are left untouched."""
    try:
        return [a.with_overrides(overrides.get(a.name, {})) for a in analyzers]
    except ValidationError as exc:  # defence in depth: validate_overrides should have caught it
        raise InvalidTuningError(str(exc)) from exc
