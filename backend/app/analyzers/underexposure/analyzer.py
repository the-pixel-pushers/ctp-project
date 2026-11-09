"""Underexposure detection from the luma histogram.

A photo is UNDEREXPOSED only when it is dark overall *and* a large share of its pixels is
crushed to black, so deliberately low-key shots (night skylines) that keep shadow detail
are not flagged.
"""

from app.analyzers.base import AnalysisResult, Analyzer
from app.analyzers.luma import fraction_in_range, histogram_mean, severity
from app.analyzers.underexposure.settings import UnderexposureSettings
from app.imaging import PreparedImage


class UnderexposureAnalyzer(Analyzer):
    name = "underexposure"

    def __init__(self, settings: UnderexposureSettings | None = None) -> None:
        self.settings = settings or UnderexposureSettings()

    def analyze(self, image: PreparedImage) -> AnalysisResult:
        s = self.settings
        histogram = image.luma_histogram
        average = histogram_mean(histogram)
        highlights = fraction_in_range(histogram, 250, 255)
        shadows = fraction_in_range(histogram, 0, s.shadow_level)

        underexposed = average < s.brightness_threshold and shadows > s.shadow_ratio
        # Darkness is measured from white so that 0 brightness is the most severe.
        level = min(
            severity(255.0 - average, 255.0 - s.brightness_threshold, 255.0),
            severity(shadows, s.shadow_ratio, 1.0),
        )
        return AnalysisResult(
            flag="UNDEREXPOSED" if underexposed else "OK",
            score=round(1.0 - level, 4),
            metrics={
                "average_brightness": round(average, 2),
                "highlight_ratio": round(highlights, 4),
                "shadow_ratio": round(shadows, 4),
            },
        )
