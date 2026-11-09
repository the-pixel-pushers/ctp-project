from app.analyzers.underexposure import UnderexposureAnalyzer
from app.imaging import PreparedImage
from tests.conftest import solid_image, split_image


def run(img):
    return UnderexposureAnalyzer().analyze(PreparedImage(img))


def test_black_image_is_underexposed():
    result = run(solid_image(0))
    assert result.flag == "UNDEREXPOSED"
    assert 0.0 <= result.score < 0.5
    assert result.metrics["shadow_ratio"] == 1.0
    assert set(result.metrics) == {"average_brightness", "highlight_ratio", "shadow_ratio"}


def test_midtone_image_is_ok():
    result = run(solid_image(128))
    assert result.flag == "OK"
    assert result.score >= 0.5


def test_dark_without_crushed_shadows_is_ok():
    # Low-key: dark overall but no pixel is at or below the shadow level.
    result = run(solid_image(30))
    assert result.metrics["average_brightness"] < 65
    assert result.metrics["shadow_ratio"] == 0.0
    assert result.flag == "OK"


def test_crushed_shadows_without_dark_average_is_ok():
    # 50% black but the average is ~127, so not "dark overall".
    assert run(split_image(0.5)).flag == "OK"


def test_bright_image_is_ok():
    assert run(solid_image(240)).flag == "OK"


def test_score_decreases_with_more_crushing():
    mostly_black = run(split_image(0.1))
    all_black = run(solid_image(0))
    assert mostly_black.flag == "UNDEREXPOSED"
    assert all_black.score <= mostly_black.score
