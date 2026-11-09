"""Helpers shared by the exposure analyzers. They only read the cached luma histogram."""

import numpy as np

LEVELS = np.arange(256, dtype=np.float64)


def histogram_mean(histogram: np.ndarray) -> float:
    """Mean luma (0-255) from a 256-bin histogram."""
    total = histogram.sum()
    return float(histogram @ LEVELS / total) if total else 0.0


def fraction_in_range(histogram: np.ndarray, low: int, high: int) -> float:
    """Fraction of pixels whose luma is in [low, high] (inclusive)."""
    total = histogram.sum()
    return float(histogram[low : high + 1].sum() / total) if total else 0.0


def severity(value: float, threshold: float, maximum: float) -> float:
    """Piecewise-linear map to [0, 1]: `threshold` is 0.5, 0 is 0.0 and `maximum` is 1.0.

    A flagged image has every severity input above its threshold, so min() of the inputs
    is above 0.5 exactly when the flag is raised, which keeps `score = 1 - severity` below
    0.5 for flagged images and at or above 0.5 for the rest.
    """
    if value <= 0:
        return 0.0
    if value <= threshold:
        return 0.5 * value / threshold
    if maximum <= threshold:
        return 1.0
    return min(1.0, 0.5 + 0.5 * (value - threshold) / (maximum - threshold))
