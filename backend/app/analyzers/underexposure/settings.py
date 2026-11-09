from pydantic_settings import BaseSettings, SettingsConfigDict


class UnderexposureSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHOTOSORT_UNDEREXPOSURE_", env_file=".env", extra="ignore")

    # Mean luma (0-255) below which the photo counts as dark overall.
    brightness_threshold: float = 65.0
    # A pixel is a crushed shadow when its luma is at or below this level.
    shadow_level: int = 5
    # Fraction of crushed shadows above which the photo is UNDEREXPOSED (together with darkness).
    shadow_ratio: float = 0.10
