"""Blur detection via OpenCV Laplacian variance."""

import cv2
import numpy as np

from app.analyzers.base import AnalysisResult, Analyzer
from app.analyzers.blur.settings import BlurSettings
from app.imaging import PreparedImage


def laplacian_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def normalize_score(variance: float, threshold: float) -> float:
    """Map variance to [0, 1] with a saturating curve where `threshold` maps to 0.5."""
    if variance <= 0:
        return 0.0
    score = variance / (variance + threshold)
    return round(min(max(score, 0.0), 1.0), 4)


class BlurAnalyzer(Analyzer):
    name = "blur"

    def __init__(self, settings: BlurSettings | None = None) -> None:
        self.settings = settings or BlurSettings()

    def analyze(self, image: PreparedImage) -> AnalysisResult:
        threshold = self.settings.threshold
        variance = laplacian_variance(image.gray)
        return AnalysisResult(
            flag="BLURRY" if variance < threshold else "ACCEPTABLE",
            score=normalize_score(variance, threshold),
            metrics={"laplacian_variance": round(variance, 2)},
        )
