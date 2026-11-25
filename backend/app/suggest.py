"""Predict the best scene preset for a batch from the metrics the analyzers already return.

Each photo is reduced to a few yes/no indicators (dark, crushed shadows, small sharp subject on a
soft background, ...). Each scene preset has a rule over those indicators, and its evidence is the
share of the batch that matches. The strongest qualifying preset is suggested; none qualifying
means "stay on Default".

Exposure metrics (`average_brightness`, `highlight_ratio`, `shadow_ratio`) do not depend on the
user's tuning. Blur metrics do (`grid_cols`, `threshold`), so the thresholds below assume the batch
was analyzed with default settings; the frontend only asks for a suggestion in that case.

Only scene presets are eligible. Strict/Lenient cull express user intent, and Sports/Macro can't be
told apart reliably from these metrics, so they are never suggested.

All thresholds are starting points: calibrate them on real shoots with `scripts/suggest_report.py`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.schemas import PhotoMetrics, PresetAlternative, PresetSuggestion

# --- per-photo indicator thresholds ----------------------------------------------------------------
DARK_BRIGHTNESS = 80.0  # mean luma below this: dark overall (matches the underexposure default)
BRIGHT_BRIGHTNESS = 160.0  # mean luma above this: bright overall (matches the overexposure default)
CRUSHED_SHADOW_RATIO = 0.06  # share of near-black pixels above this: crushed shadows
BLOWN_HIGHLIGHT_RATIO = 0.06  # share of near-white pixels above this: large blown areas
POINT_LIGHT_RATIO = 0.01  # share of near-white pixels above this: visible light sources
MIN_SUBJECT_FOCUS_RATIO = 8.0  # subject at least this many times sharper than the background
TINY_SUBJECT_AREA = 0.08  # sharp share of informative tiles below this: tiny subject
SMALL_SUBJECT_AREA = 0.40  # ... below this (and >= tiny): small subject (0.40 = default SHARP cutoff)
# Open sky: the top third has under this share of the bottom third's detail and is brighter. On the
# test sets this matched 63% of landscapes vs 25% of birds, 32% of concerts and 5% of sport photos.
SKY_TOP_DETAIL_RATIO = 0.5

# --- batch selection -------------------------------------------------------------------------------
MIN_BATCH = 3  # smaller batches say too little about the session
MIN_MATCHED = 3  # a preset needs at least this many matching photos ...
MIN_SHARE = 0.40  # ... and at least this share of the batch
ALTERNATIVE_SHARE = 0.25  # runners-up at or above this share are listed as alternatives


@dataclass(frozen=True, slots=True)
class Indicators:
    dark: bool = False
    crushed: bool = False
    bright: bool = False
    blown: bool = False
    point_lights: bool = False
    tiny_subject: bool = False
    small_subject: bool = False
    sky_top: bool = False


def _above(value: float | None, threshold: float) -> bool:
    return value is not None and value > threshold


def _below(value: float | None, threshold: float) -> bool:
    return value is not None and value < threshold


def indicators(photo: PhotoMetrics) -> Indicators:
    """Missing analyzers or metrics simply leave the related indicators False."""
    over = photo.metrics.get("overexposure", {})
    under = photo.metrics.get("underexposure", {})
    blur = photo.metrics.get("blur", {})
    brightness = over.get("average_brightness", under.get("average_brightness"))
    highlights = over.get("highlight_ratio", under.get("highlight_ratio"))
    shadows = under.get("shadow_ratio", over.get("shadow_ratio"))

    blur_flag = photo.flags.get("blur")
    sharp_area = blur.get("sharp_area")
    subject_on_soft_bg = (
        blur_flag in ("BLURRY", "SHALLOW_FOCUS")
        and blur.get("subject_tiles", 0) >= 1
        and blur.get("focus_ratio", 0) >= MIN_SUBJECT_FOCUS_RATIO
        and sharp_area is not None
    )
    return Indicators(
        dark=_below(brightness, DARK_BRIGHTNESS),
        crushed=_above(shadows, CRUSHED_SHADOW_RATIO),
        bright=_above(brightness, BRIGHT_BRIGHTNESS),
        blown=_above(highlights, BLOWN_HIGHLIGHT_RATIO),
        point_lights=_above(highlights, POINT_LIGHT_RATIO),
        tiny_subject=subject_on_soft_bg and sharp_area < TINY_SUBJECT_AREA,
        small_subject=subject_on_soft_bg and TINY_SUBJECT_AREA <= sharp_area < SMALL_SUBJECT_AREA,
        sky_top=_below(blur.get("top_detail_ratio"), SKY_TOP_DETAIL_RATIO)
        and _above(blur.get("top_brightness_gain"), 0.0),
    )


@dataclass(frozen=True, slots=True)
class Rule:
    preset_id: str
    matches: Callable[[Indicators], bool]
    reason: str  # completes "N of M photos ..."


# Listed in tie-break priority: more specific scenes first.
RULES: list[Rule] = [
    Rule("wildlife", lambda i: i.tiny_subject, "have a tiny sharp subject on a soft background"),
    Rule("concert_events", lambda i: i.dark and i.point_lights, "are dark with bright point lights"),
    Rule("portrait_bokeh", lambda i: i.small_subject, "have a small sharp subject on a soft background"),
    Rule(
        "night_lowkey",
        lambda i: i.dark and i.crushed and not i.point_lights,
        "are dark with crushed shadows",
    ),
    Rule("high_key", lambda i: i.bright and i.blown, "are bright with large highlight areas"),
    Rule("landscape", lambda i: i.sky_top, "have open sky or smooth areas above a detailed scene"),
]


def suggest_preset(photos: Sequence[PhotoMetrics]) -> PresetSuggestion | None:
    total = len(photos)
    if total < MIN_BATCH:
        return None
    marks = [indicators(p) for p in photos]
    scored = [(rule, sum(rule.matches(m) for m in marks)) for rule in RULES]
    # Stable sort keeps RULES order for ties.
    ranked = sorted(scored, key=lambda item: -item[1])
    best, matched = ranked[0]
    if matched < MIN_MATCHED or matched / total < MIN_SHARE:
        return None
    return PresetSuggestion(
        preset_id=best.preset_id,
        confidence=round(matched / total, 3),
        matched=matched,
        total=total,
        reasons=[f"{matched} of {total} photos {best.reason}"],
        alternatives=[
            PresetAlternative(preset_id=rule.preset_id, confidence=round(n / total, 3))
            for rule, n in ranked[1:]
            if n >= 2 and n / total >= ALTERNATIVE_SHARE
        ],
    )
