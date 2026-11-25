"""Contract every image analyzer implements.

Analyzers must be pure and thread-safe: they run concurrently in a thread pool, must not
decode or resize (use the PreparedImage they are given), and should raise on failure
rather than return partial results.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

from app.imaging import PreparedImage


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    flag: str
    score: float  # 0.0-1.0, higher is better
    metrics: dict[str, float] = field(default_factory=dict)


class Analyzer(ABC):
    name: ClassVar[str]  # key under `analyses` in the API response

    @abstractmethod
    def analyze(self, image: PreparedImage) -> AnalysisResult: ...

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Analyzer":
        """A new analyzer whose `settings` are this one's with `overrides` applied (re-validated).
        Never mutates `self`, so shared instances stay thread-safe. Analyzers without a `settings`
        attribute are returned unchanged."""
        settings = getattr(self, "settings", None)
        if not overrides or settings is None:
            return self
        return type(self)(type(settings)(**{**settings.model_dump(), **overrides}))
