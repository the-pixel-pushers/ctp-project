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


def encode(img: np.ndarray, ext: str) -> bytes:
    ok, buf = cv2.imencode(ext, img)
    assert ok
    return buf.tobytes()


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c
