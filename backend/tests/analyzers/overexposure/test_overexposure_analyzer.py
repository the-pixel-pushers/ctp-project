from app.analyzers.overexposure import OverexposureAnalyzer
from app.imaging import PreparedImage
from tests.conftest import solid_image, split_image


def run(img):
    return OverexposureAnalyzer().analyze(PreparedImage(img))


def test_blown_out_image_is_overexposed():
    result = run(solid_image(255))
    assert result.flag == "OVEREXPOSED"
    assert 0.0 <= result.score < 0.5
    assert result.metrics["highlight_ratio"] == 1.0
    assert set(result.metrics) == {"average_brightness", "highlight_ratio", "shadow_ratio"}


def test_midtone_image_is_ok():
    result = run(solid_image(128))
    assert result.flag == "OK"
    assert result.score >= 0.5


def test_bright_without_clipping_is_ok():
    # High-key: bright overall but no pixel reaches the highlight level.
    result = run(solid_image(200))
    assert result.metrics["average_brightness"] > 190
    assert result.metrics["highlight_ratio"] == 0.0
    assert result.flag == "OK"


def test_clipping_without_bright_average_is_ok():
    # 5% blown out, rest black: average is low and highlights are under the ratio.
    assert run(split_image(0.05)).flag == "OK"
    # 50% blown out but average is only ~127, so not "bright overall".
    assert run(split_image(0.5)).flag == "OK"


def test_dark_image_is_ok():
    assert run(solid_image(10)).flag == "OK"


def test_score_decreases_with_more_clipping():
    mostly_white = run(split_image(0.9))
    all_white = run(solid_image(255))
    assert mostly_white.flag == "OVEREXPOSED"
    assert all_white.score <= mostly_white.score
