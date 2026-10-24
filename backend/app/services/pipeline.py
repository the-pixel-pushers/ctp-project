"""Synchronous per-image pipeline, executed inside the thread pool."""

import logging
from collections.abc import Sequence

from app.analyzers.base import Analyzer
from app.imaging import prepare_image
from app.schemas.cull import AnalysisOut

logger = logging.getLogger(__name__)


def run_pipeline(data: bytes, analyzers: Sequence[Analyzer], max_width: int) -> dict[str, AnalysisOut]:
    """Decode once, then run every analyzer. Raises ImageDecodeError if the image is unreadable;
    a failing analyzer is reported in its own entry without affecting the others."""
    image = prepare_image(data, max_width)
    outcomes: dict[str, AnalysisOut] = {}
    for analyzer in analyzers:
        try:
            result = analyzer.analyze(image)
            outcomes[analyzer.name] = AnalysisOut(
                status="success", flag=result.flag, score=result.score, metrics=result.metrics
            )
        except Exception:
            logger.exception("Analyzer %r failed", analyzer.name)
            outcomes[analyzer.name] = AnalysisOut(status="error", error="Analyzer failed on this image")
    return outcomes
