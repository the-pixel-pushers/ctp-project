"""The single place analyzers are switched on. Adding a feature = one import + one line."""

from app.analyzers.base import Analyzer
from app.analyzers.blur import BlurAnalyzer
from app.analyzers.overexposure import OverexposureAnalyzer
from app.analyzers.scene import SceneAnalyzer
from app.analyzers.underexposure import UnderexposureAnalyzer


def build_analyzers() -> list[Analyzer]:
    analyzers: list[Analyzer] = [
        BlurAnalyzer(),
        OverexposureAnalyzer(),
        UnderexposureAnalyzer(),
        SceneAnalyzer(),  # informational: metrics for preset suggestions, flag always OK
    ]
    names = [a.name for a in analyzers]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise RuntimeError(f"Duplicate analyzer names: {sorted(duplicates)}")
    return analyzers
