
import cv2
import numpy as np


def calculate_exposure_metrics(image):
    """
    Calculate image brightness and clipping metrics.
    Expects an 8-bit, 3-channel BGR image from OpenCV.
    """
    if (
        image is None
        or not isinstance(image, np.ndarray)
        or image.ndim != 3
        or image.shape[2] != 3
        or image.dtype != np.uint8
        or image.size == 0
    ):
        raise ValueError("Expected a non-empty 8-bit BGR image")

    # Convert image to YCrCb color space.
    # The Y channel represents luma (brightness).
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
    brightness = ycrcb[:, :, 0]

    average_brightness = float(np.mean(brightness))

    # Fraction of pixels close to white or black.
    highlight_ratio = float(np.mean(brightness >= 250))
    shadow_ratio = float(np.mean(brightness <= 5))

    return {
        "average_brightness": round(average_brightness, 2),
        "highlight_ratio": round(highlight_ratio, 4),
        "shadow_ratio": round(shadow_ratio, 4),
    }


def detect_exposure(image):
    """
    Classify exposure as overexposed, underexposed,
    or acceptable using experimental thresholds.
    """
    metrics = calculate_exposure_metrics(image)

    avg = metrics["average_brightness"]
    highlights = metrics["highlight_ratio"]
    shadows = metrics["shadow_ratio"]

    if avg > 190 and highlights > 0.10:
        classification = "overexposed"

    elif avg < 65 and shadows > 0.10:
        classification = "underexposed"

    else:
        classification = "acceptable"

    return {
        "classification": classification,
        **metrics,
    }
