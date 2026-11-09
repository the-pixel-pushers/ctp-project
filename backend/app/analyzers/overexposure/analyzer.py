"""Overexposure detection from the luma histogram.

A photo is OVEREXPOSED only when it is bright overall *and* a large share of its pixels is
blown out. Either condition alone is not enough, so deliberately high-key shots (snow, white
backdrops) with intact highlights detail are not flagged.
"""

from app.analyzers.base import AnalysisResult, Analyzer
from app.analyzers.luma import fraction_in_range, histogram_mean, severity
from app.analyzers.overexposure.settings import OverexposureSettings
from app.imaging import PreparedImage


class OverexposureAnalyzer(Analyzer):
    name = "overexposure"

    def __init__(self, settings: OverexposureSettings | None = None) -> None:
        self.settings = settings or OverexposureSettings()

    def analyze(self, image: PreparedImage) -> AnalysisResult:
        s = self.settings
        histogram = image.luma_histogram
        average = histogram_mean(histogram)
        highlights = fraction_in_range(histogram, s.highlight_level, 255)
        shadows = fraction_in_range(histogram, 0, 5)

        overexposed = average > s.brightness_threshold and highlights > s.highlight_ratio
        level = min(
            severity(average, s.brightness_threshold, 255.0),
            severity(highlights, s.highlight_ratio, 1.0),
        )
        return AnalysisResult(
            flag="OVEREXPOSED" if overexposed else "OK",
            score=round(1.0 - level, 4),
            metrics={
                "average_brightness": round(average, 2),
                "highlight_ratio": round(highlights, 4),
                "shadow_ratio": round(shadows, 4),
            },
        )
