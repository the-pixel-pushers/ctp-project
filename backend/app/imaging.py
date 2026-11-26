"""Shared image loading. Every analyzer receives the same PreparedImage, so bytes are
decoded, resized and converted to grayscale at most once per upload."""

import threading
from functools import cached_property
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np
from PIL import Image


class ImageDecodeError(ValueError):
    """Raised when bytes cannot be decoded into an image."""


# YuNet face detector (OpenCV model zoo, MIT licence, ~230 KB). Faces are found on a copy of the proxy
# scaled to this width: ~6 ms per photo, and on the 67 calibration photos it found more faces (39 vs
# 31) than detecting on the full 1000 px proxy, which takes ~35 ms.
FACE_MODEL = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"
FACE_DETECT_WIDTH = 320
FACE_MIN_SCORE = 0.7
_face_detectors = threading.local()  # cv2.FaceDetectorYN is not thread-safe: one per worker thread


class Face(NamedTuple):
    """Detected face box in proxy pixel coordinates, plus the detector's confidence (0-1)."""

    x: int
    y: int
    width: int
    height: int
    score: float


def detect_faces(proxy: np.ndarray) -> list[Face]:
    """Faces in a BGR proxy, largest first. Raises if the model can't be loaded."""
    height, width = proxy.shape[:2]
    scale = min(1.0, FACE_DETECT_WIDTH / width)
    small = proxy
    if scale < 1.0:
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        small = cv2.resize(proxy, size, interpolation=cv2.INTER_AREA)
    detector = getattr(_face_detectors, "detector", None)
    if detector is None:
        detector = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (320, 320), FACE_MIN_SCORE)
        _face_detectors.detector = detector
    detector.setInputSize((small.shape[1], small.shape[0]))
    _, raw = detector.detect(small)
    if raw is None:
        return []
    faces = []
    for row in raw:
        x, y, w, h = (float(v) / scale for v in row[:4])
        x0, y0 = max(0, round(x)), max(0, round(y))
        x1, y1 = min(width, round(x + w)), min(height, round(y + h))
        if x1 > x0 and y1 > y0:
            faces.append(Face(x0, y0, x1 - x0, y1 - y0, float(row[-1])))
    return sorted(faces, key=lambda f: f.width * f.height, reverse=True)


class PreparedImage:
    """Downsampled working proxy of an uploaded image (BGR, uint8), plus the original bytes so
    metadata (EXIF) can be read. `raw` is None when built directly from pixels (tests)."""

    def __init__(self, proxy: np.ndarray, raw: bytes | None = None) -> None:
        self.proxy = proxy
        self.raw = raw

    @cached_property
    def exif(self) -> dict[str, float]:
        """Camera settings from EXIF, only the keys present (see `read_exif`). {} if none."""
        return read_exif(self.raw) if self.raw else {}

    @cached_property
    def gray(self) -> np.ndarray:
        return cv2.cvtColor(self.proxy, cv2.COLOR_BGR2GRAY)

    @cached_property
    def faces(self) -> list[Face]:
        """Detected faces, largest first (see `detect_faces`). Only computed when an analyzer asks."""
        return detect_faces(self.proxy)

    @cached_property
    def luma_histogram(self) -> np.ndarray:
        """256-bin histogram of the Y (luma) channel of YCrCb, shared by the exposure analyzers."""
        luma = cv2.cvtColor(self.proxy, cv2.COLOR_BGR2YCrCb)[:, :, 0]
        return np.bincount(luma.ravel(), minlength=256)


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
    return PreparedImage(make_proxy(decode_image(data), max_width), raw=data)


# EXIF tag ids (Exif sub-IFD unless noted).
_EXIF_IFD = 0x8769
_TAGS = {
    0x829A: "exposure_time",  # seconds
    0x829D: "f_number",
    0x8827: "iso",
    0x920A: "focal_length",  # mm, real (not 35mm-equivalent)
    0xA405: "focal_length_35mm",
    0x9206: "subject_distance",  # metres
}
_LENS_MODEL = 0xA434


def _as_float(value: object) -> float | None:
    if isinstance(value, tuple):  # some cameras store a sequence, e.g. ISO
        value = value[0] if value else None
    try:
        number = float(value)  # IFDRational, int and float all convert
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return number if np.isfinite(number) and number > 0 else None


def read_exif(data: bytes) -> dict[str, float]:
    """Camera settings from a JPEG/PNG's EXIF, keyed as in `_TAGS` (plus `macro_lens` = 1.0 when the
    lens model says macro). Only present, positive values are returned. Never raises: files
    without EXIF (or with broken EXIF) give {}. Web downloads are usually stripped."""
    try:
        with Image.open(BytesIO(data)) as img:  # reads the header only, not the pixels
            exif = img.getexif()
            tags = {**exif, **exif.get_ifd(_EXIF_IFD)}
    except Exception:
        return {}
    out = {name: v for tag, name in _TAGS.items() if (v := _as_float(tags.get(tag))) is not None}
    lens = tags.get(_LENS_MODEL)
    if isinstance(lens, str) and "macro" in lens.lower():
        out["macro_lens"] = 1.0
    return out
