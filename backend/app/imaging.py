"""Shared image loading. Every analyzer receives the same PreparedImage, so bytes are
decoded, resized and converted to grayscale at most once per upload."""

from functools import cached_property

import cv2
import numpy as np


class ImageDecodeError(ValueError):
    """Raised when bytes cannot be decoded into an image."""


class PreparedImage:
    """Downsampled working proxy of an uploaded image (BGR, uint8)."""

    def __init__(self, proxy: np.ndarray) -> None:
        self.proxy = proxy

    @cached_property
    def gray(self) -> np.ndarray:
        return cv2.cvtColor(self.proxy, cv2.COLOR_BGR2GRAY)


def decode_image(data: bytes) -> np.ndarray:
    if not data:
        raise ImageDecodeError("Empty file")
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ImageDecodeError("File is corrupted or not a supported image")
    return img


def make_proxy(img: np.ndarray, max_width: int) -> np.ndarray:
    """Downsample to at most `max_width` px wide, preserving aspect ratio."""
    height, width = img.shape[:2]
    if width <= max_width:
        return img
    scale = max_width / width
    return cv2.resize(img, (max_width, max(1, round(height * scale))), interpolation=cv2.INTER_AREA)


def prepare_image(data: bytes, max_width: int) -> PreparedImage:
    return PreparedImage(make_proxy(decode_image(data), max_width))
