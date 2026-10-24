import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Shared runtime configuration. Every field can be overridden via a PHOTOSORT_* env var.
    Analyzer-specific settings live in each analyzer's own package (e.g. analyzers/blur/settings.py)."""

    model_config = SettingsConfigDict(env_prefix="PHOTOSORT_", env_file=".env", extra="ignore")

    app_name: str = "PhotoSort API"

    # Working proxy every analyzer receives
    proxy_max_width: int = 1000

    # Concurrency
    max_workers: int = os.cpu_count() or 4

    # Upload limits
    max_files_per_batch: int = 100
    max_file_bytes: int = 25 * 1024 * 1024
    allowed_content_types: frozenset[str] = frozenset({"image/jpeg", "image/png"})
    allowed_extensions: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
