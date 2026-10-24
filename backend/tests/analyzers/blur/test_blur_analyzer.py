import pytest

from app.analyzers.blur import BlurAnalyzer, BlurSettings
from app.analyzers.blur.analyzer import normalize_score
from app.imaging import PreparedImage
from tests.conftest import blurry_image, sharp_image

THRESHOLD = 80.0


@pytest.fixture
def analyzer():
    return BlurAnalyzer(BlurSettings(threshold=THRESHOLD))


def test_sharp_image_is_acceptable(analyzer):
    result = analyzer.analyze(PreparedImage(sharp_image()))
    assert result.flag == "ACCEPTABLE"
    assert result.score > 0.5


def test_blurry_image_is_flagged(analyzer):
    result = analyzer.analyze(PreparedImage(blurry_image()))
    assert result.flag == "BLURRY"
    assert result.score < 0.5
    assert result.metrics["laplacian_variance"] < THRESHOLD


@pytest.mark.parametrize(
    ("variance", "expected"),
    [(0.0, 0.0), (80.0, 0.5), (45.2, 0.361), (1e9, 1.0)],
)
def test_normalize_score(variance, expected):
    assert normalize_score(variance, THRESHOLD) == pytest.approx(expected, abs=1e-3)
