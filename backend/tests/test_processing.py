import pytest

from app.analyzers.base import AnalysisResult, Analyzer
from app.analyzers.blur import BlurAnalyzer
from app.imaging import ImageDecodeError, PreparedImage
from app.processing import run_pipeline
from tests.conftest import encode, sharp_image


class ExplodingAnalyzer(Analyzer):
    name = "exploding"

    def analyze(self, image: PreparedImage) -> AnalysisResult:
        raise RuntimeError("boom")


def test_failing_analyzer_does_not_affect_others():
    outcomes = run_pipeline(encode(sharp_image(), ".png"), [BlurAnalyzer(), ExplodingAnalyzer()], 1000)
    assert outcomes["blur"].status == "success"
    assert outcomes["blur"].flag == "ACCEPTABLE"
    assert outcomes["exploding"].status == "error"
    assert outcomes["exploding"].error


def test_corrupt_image_raises():
    with pytest.raises(ImageDecodeError):
        run_pipeline(b"garbage", [BlurAnalyzer()], 1000)
