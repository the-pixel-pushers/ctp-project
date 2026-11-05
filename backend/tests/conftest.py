import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def sharp_image(width: int = 800, height: int = 600) -> np.ndarray:
    """High-frequency checkerboard + noise: very high Laplacian variance."""
    rng = np.random.default_rng(42)
    yy, xx = np.indices((height, width))
    board = (((xx // 8) + (yy // 8)) % 2 * 255).astype(np.uint8)
    noise = rng.integers(0, 40, size=(height, width), dtype=np.uint8)
    gray = cv2.add(board, noise)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def blurry_image(width: int = 800, height: int = 600) -> np.ndarray:
    return cv2.GaussianBlur(sharp_image(width, height), (31, 31), 10)


def soft_background(width: int = 800, height: int = 600) -> np.ndarray:
    """Out-of-focus scene: smooth low-frequency shapes plus faint sensor noise.

    Unlike `blurry_image()`, which blurs down to an almost uniform gray, this keeps the
    tonal structure a real bokeh background has, so its tiles count as informative."""
    rng = np.random.default_rng(7)
    yy, xx = np.indices((height, width), dtype=np.float64)
    shapes = 128 + 50 * np.sin(xx / 37.0) * np.cos(yy / 53.0) + 30 * np.sin((xx + yy) / 71.0)
    noise = rng.normal(0, 1.5, size=(height, width))
    gray = np.clip(shapes + noise, 0, 255).astype(np.uint8)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def bokeh_image(
    box: tuple[int, int, int, int], width: int = 800, height: int = 600, flat: bool = False
) -> np.ndarray:
    """In-focus subject at `box` = (x, y, w, h) on a soft background (or a flat one)."""
    img = np.full((height, width, 3), 128, dtype=np.uint8) if flat else soft_background(width, height)
    x, y, w, h = box
    img[y : y + h, x : x + w] = sharp_image(width, height)[y : y + h, x : x + w]
    return img


def encode(img: np.ndarray, ext: str) -> bytes:
    ok, buf = cv2.imencode(ext, img)
    assert ok
    return buf.tobytes()


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c
