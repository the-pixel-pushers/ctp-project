"""Calibrate the preset-suggestion thresholds on real photos.

Runs every analyzer (default settings) over the JPG/PNG files in a folder and prints, per photo, the
metrics the suggestion rules read and which indicators fired, then the batch suggestion.

    .venv\\Scripts\\python -m scripts.suggest_report path\\to\\shoot

Adjust the constants at the top of `app/suggest.py` until each kind of shoot gets the right preset.
"""

import sys
from dataclasses import asdict
from pathlib import Path

from app.analyzers.registry import build_analyzers
from app.config import get_settings
from app.imaging import ImageDecodeError
from app.processing import run_pipeline
from app.schemas import PhotoMetrics
from app.suggest import indicators, suggest_preset

EXTENSIONS = {".jpg", ".jpeg", ".png"}


def main(folder: Path) -> None:
    analyzers = build_analyzers()
    max_width = get_settings().proxy_max_width
    photos: list[PhotoMetrics] = []
    for path in sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS):
        try:
            analyses = run_pipeline(path.read_bytes(), analyzers, max_width)
        except ImageDecodeError as exc:
            print(f"{path.name}: skipped ({exc})")
            continue
        photo = PhotoMetrics(
            flags={name: a.flag or "ERROR" for name, a in analyses.items()},
            metrics={name: a.metrics for name, a in analyses.items()},
        )
        photos.append(photo)
        blur = photo.metrics.get("blur", {})
        over = photo.metrics.get("overexposure", {})
        under = photo.metrics.get("underexposure", {})
        fired = [name for name, on in asdict(indicators(photo)).items() if on]
        print(
            f"{path.name}: blur={photo.flags.get('blur')} sharp_area={blur.get('sharp_area')} "
            f"focus_ratio={blur.get('focus_ratio')} subject_tiles={blur.get('subject_tiles')} "
            f"top_detail={blur.get('top_detail_ratio')} top_gain={blur.get('top_brightness_gain')} "
            f"brightness={over.get('average_brightness')} highlights={over.get('highlight_ratio')} "
            f"shadows={under.get('shadow_ratio')} -> {', '.join(fired) or '-'}"
        )

    print()
    suggestion = suggest_preset(photos)
    if suggestion is None:
        print(f"Suggestion for {len(photos)} photos: none (stay on Default)")
        return
    print(
        f"Suggestion: {suggestion.preset_id} ({suggestion.confidence:.0%}): {'; '.join(suggestion.reasons)}"
    )
    for alt in suggestion.alternatives:
        print(f"  alternative: {alt.preset_id} ({alt.confidence:.0%})")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit("usage: python -m scripts.suggest_report <folder>")
    main(Path(sys.argv[1]))
