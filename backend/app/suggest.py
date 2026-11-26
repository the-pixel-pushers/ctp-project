"""Predict the best preset for a batch from the metrics the analyzers already return.

Each photo is reduced to yes/no indicators. Pixel indicators come from the blur, exposure and scene
analyzers; EXIF indicators from camera settings (scene analyzer `exif_*` metrics), when present.
Each preset has a `Rule`: a photo matches it if its pixel predicate *or* its EXIF predicate holds.

Selection is **priority-first**: rules are checked from the most specific scene to the most
generic, and the first one matching enough of the batch wins. Concert and sport photos also look
like "a subject on a soft background", so picking the largest share would wrongly favor Portrait.
Other rules with a meaningful share are returned as alternatives.

Calibration (pixel rules) on the user's test folders, share of photos matching:

    rule (pixel)                        landscapes  birds  Concert  sport
    concert: dark + vivid colored light      4%       8%     48%     15%
    sports: soft texture + darker top        4%      15%      8%     65%
    landscape: open sky at the top          63%      25%     32%      5%

EXIF rules follow common photography conventions and are **unverified**: none of the test photos
carried camera settings (web downloads are stripped). They only fire on camera originals.

Known limit: pixels can't tell birds from people. Without EXIF a bird batch reads as Portrait /
bokeh (Wildlife when the subjects are tiny); a telephoto focal length in EXIF fixes that.

Exposure and scene metrics don't depend on the user's tuning; blur metrics do, so the thresholds
assume default settings and the frontend only asks for batches analyzed with defaults. Calibrate on
real folders with `scripts/suggest_report.py`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.schemas import PhotoMetrics, PresetAlternative, PresetSuggestion

# --- pixel indicator thresholds ---------------------------------------------------------------------
DARK_BRIGHTNESS = 80.0  # mean luma below this: dark overall (matches the underexposure default)
BRIGHT_BRIGHTNESS = 160.0  # mean luma above this: bright overall (matches the overexposure default)
CRUSHED_SHADOW_RATIO = 0.06  # share of near-black pixels above this: crushed shadows
BLOWN_HIGHLIGHT_RATIO = 0.06  # share of near-white pixels above this: large blown areas
POINT_LIGHT_RATIO = 0.01  # share of near-white pixels above this: visible light sources
MIN_SUBJECT_FOCUS_RATIO = 8.0  # subject at least this many times sharper than the background
TINY_SUBJECT_AREA = 0.08  # sharp share of informative tiles below this: tiny subject
SUBJECT_MAX_AREA = 0.60  # above this the whole frame is sharp: not "a subject on a soft background"
# Open sky: the top third has under this share of the bottom third's detail and is brighter.
SKY_TOP_DETAIL_RATIO = 0.5
# Concert: a largely black frame lit by saturated colored light (stage lighting rarely clips white).
CONCERT_DARK_SHARE = 0.25
CONCERT_VIVID_LIGHT = 0.01
# Sports: much of the frame is textured but soft (blurred crowds, panning streaks), and the top is
# darker than the bottom (stands and crowds above a lit field or track).
ACTION_SOFT_TEXTURE = 0.40

# --- EXIF indicator thresholds (photography conventions, unverified on real camera files) -------------
TELEPHOTO_MM = 300.0  # 35mm-equivalent focal length
FAST_SHUTTER_S = 1 / 1000
HIGH_ISO = 3200.0
LONG_EXPOSURE_S = 1.0
MACRO_DISTANCE_M = 0.3
LANDSCAPE_MIN_F = 8.0
LANDSCAPE_MAX_MM = 35.0
PORTRAIT_MAX_F = 2.8
PORTRAIT_MM = (50.0, 135.0)

# --- batch selection -------------------------------------------------------------------------------
MIN_BATCH = 3  # smaller batches say too little about the session
MIN_MATCHED = 3  # a preset needs at least this many matching photos ...
MIN_SHARE = 0.40  # ... and at least this share of the batch
ALTERNATIVE_MATCHED = 2
ALTERNATIVE_SHARE = 0.25  # other rules at or above this share are listed as alternatives


@dataclass(frozen=True, slots=True)
class Indicators:
    # pixels
    dark: bool = False
    crushed: bool = False
    bright: bool = False
    blown: bool = False
    point_lights: bool = False
    subject_on_soft: bool = False
    tiny_subject: bool = False
    sky_top: bool = False
    concert_lights: bool = False
    action: bool = False
    # EXIF
    telephoto: bool = False
    fast_shutter: bool = False
    high_iso: bool = False
    long_exposure: bool = False
    macro: bool = False
    wide_deep: bool = False
    portrait_lens: bool = False


def _above(value: float | None, threshold: float) -> bool:
    return value is not None and value > threshold


def _below(value: float | None, threshold: float) -> bool:
    return value is not None and value < threshold


def _at_least(value: float | None, threshold: float) -> bool:
    return value is not None and value >= threshold


def _at_most(value: float | None, threshold: float) -> bool:
    return value is not None and value <= threshold


def indicators(photo: PhotoMetrics) -> Indicators:
    """Missing analyzers or metrics simply leave the related indicators False."""
    over = photo.metrics.get("overexposure", {})
    under = photo.metrics.get("underexposure", {})
    blur = photo.metrics.get("blur", {})
    scene = photo.metrics.get("scene", {})
    brightness = over.get("average_brightness", under.get("average_brightness"))
    highlights = over.get("highlight_ratio", under.get("highlight_ratio"))
    shadows = under.get("shadow_ratio", over.get("shadow_ratio"))

    sharp_area = blur.get("sharp_area")
    subject_on_soft = (
        _at_least(blur.get("subject_tiles"), 1)
        and _at_least(blur.get("focus_ratio"), MIN_SUBJECT_FOCUS_RATIO)
        and _below(sharp_area, SUBJECT_MAX_AREA)
    )
    exposure = scene.get("exif_exposure_time")
    focal = scene.get("exif_focal_length_35mm")
    f_number = scene.get("exif_f_number")
    return Indicators(
        dark=_below(brightness, DARK_BRIGHTNESS),
        crushed=_above(shadows, CRUSHED_SHADOW_RATIO),
        bright=_above(brightness, BRIGHT_BRIGHTNESS),
        blown=_above(highlights, BLOWN_HIGHLIGHT_RATIO),
        point_lights=_above(highlights, POINT_LIGHT_RATIO),
        subject_on_soft=subject_on_soft,
        tiny_subject=subject_on_soft and _below(sharp_area, TINY_SUBJECT_AREA),
        sky_top=_below(blur.get("top_detail_ratio"), SKY_TOP_DETAIL_RATIO)
        and _above(blur.get("top_brightness_gain"), 0.0),
        concert_lights=_at_least(scene.get("dark_share"), CONCERT_DARK_SHARE)
        and _at_least(scene.get("vivid_light"), CONCERT_VIVID_LIGHT),
        action=_at_least(scene.get("soft_texture_share"), ACTION_SOFT_TEXTURE)
        and _below(blur.get("top_brightness_gain"), 0.0),
        telephoto=_at_least(focal, TELEPHOTO_MM),
        fast_shutter=_at_most(exposure, FAST_SHUTTER_S),
        high_iso=_at_least(scene.get("exif_iso"), HIGH_ISO),
        long_exposure=_at_least(exposure, LONG_EXPOSURE_S),
        macro=_at_most(scene.get("exif_subject_distance"), MACRO_DISTANCE_M)
        or _at_least(scene.get("exif_macro_lens"), 1.0),
        wide_deep=_at_least(f_number, LANDSCAPE_MIN_F) and _at_most(focal, LANDSCAPE_MAX_MM),
        portrait_lens=_at_most(f_number, PORTRAIT_MAX_F)
        and _at_least(focal, PORTRAIT_MM[0])
        and _at_most(focal, PORTRAIT_MM[1]),
    )


Predicate = Callable[[Indicators], bool]


@dataclass(frozen=True, slots=True)
class Rule:
    preset_id: str
    pixel: Predicate | None
    pixel_reason: str  # completes "N of M photos ..."
    exif: Predicate | None = None
    exif_reason: str = ""

    def matches(self, i: Indicators) -> bool:
        return bool((self.pixel and self.pixel(i)) or (self.exif and self.exif(i)))


# Priority order: most specific scene first, the generic "subject on a soft background" last.
RULES: list[Rule] = [
    Rule(
        "concert_events",
        lambda i: i.concert_lights,
        "are dark with vivid colored stage lighting",
        lambda i: i.high_iso and i.dark,
        "were shot at ISO 3200 or higher in the dark",
    ),
    Rule(
        "wildlife",
        lambda i: i.tiny_subject,
        "have a tiny sharp subject on a soft background",
        lambda i: i.telephoto,
        "were shot at 300 mm (35mm equivalent) or longer",
    ),
    Rule(
        "sports_action",
        lambda i: i.action,
        "have soft, busy backgrounds (crowds or panning streaks) behind the action",
        lambda i: i.fast_shutter and not i.telephoto,
        "were shot at 1/1000 s or faster",
    ),
    Rule("macro", None, "", lambda i: i.macro, "were shot very close up or with a macro lens"),
    Rule(
        "night_lowkey",
        lambda i: i.dark and i.crushed and not i.point_lights,
        "are dark with crushed shadows",
        lambda i: i.long_exposure and i.dark,
        "are dark long exposures (1 s or longer)",
    ),
    Rule("high_key", lambda i: i.bright and i.blown, "are bright with large highlight areas"),
    Rule(
        "landscape",
        lambda i: i.sky_top,
        "have open sky or smooth areas above a detailed scene",
        lambda i: i.wide_deep,
        "were shot wide (35 mm or shorter) at f/8 or narrower",
    ),
    Rule(
        "portrait_bokeh",
        # No "not sky" exclusion: birds are often shot against the sky, and landscape batches are
        # already caught by the higher-priority landscape rule.
        lambda i: i.subject_on_soft,
        "have a sharp subject on a soft background",
        lambda i: i.portrait_lens,
        "were shot at 50-135 mm with a wide aperture (f/2.8 or wider)",
    ),
]

# Never suggested: they express intent (how strict to be), not a scene.
NOT_SUGGESTED = frozenset({"default", "strict_cull", "lenient_cull"})


def _reasons(rule: Rule, marks: Sequence[Indicators], total: int) -> list[str]:
    reasons = []
    for predicate, text in ((rule.pixel, rule.pixel_reason), (rule.exif, rule.exif_reason)):
        if predicate is not None:
            n = sum(predicate(m) for m in marks)
            if n:
                reasons.append(f"{n} of {total} photos {text}")
    return reasons


def suggest_preset(photos: Sequence[PhotoMetrics]) -> PresetSuggestion | None:
    total = len(photos)
    if total < MIN_BATCH:
        return None
    marks = [indicators(p) for p in photos]
    counts = {rule.preset_id: sum(rule.matches(m) for m in marks) for rule in RULES}

    def qualifies(n: int) -> bool:
        return n >= MIN_MATCHED and n / total >= MIN_SHARE

    best = next((rule for rule in RULES if qualifies(counts[rule.preset_id])), None)
    if best is None:
        return None
    matched = counts[best.preset_id]
    others = sorted(
        (
            (rule.preset_id, n)
            for rule in RULES
            if rule is not best
            and (n := counts[rule.preset_id]) >= ALTERNATIVE_MATCHED
            and n / total >= ALTERNATIVE_SHARE
        ),
        key=lambda item: -item[1],
    )
    return PresetSuggestion(
        preset_id=best.preset_id,
        confidence=round(matched / total, 3),
        matched=matched,
        total=total,
        reasons=_reasons(best, marks, total),
        alternatives=[PresetAlternative(preset_id=pid, confidence=round(n / total, 3)) for pid, n in others],
    )
