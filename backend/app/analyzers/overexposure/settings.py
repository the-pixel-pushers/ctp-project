from pydantic_settings import BaseSettings, SettingsConfigDict


class OverexposureSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHOTOSORT_OVEREXPOSURE_", env_file=".env", extra="ignore")

    # Mean luma (0-255) above which the photo counts as bright overall.
    brightness_threshold: float = 190.0
    # A pixel is a blown highlight when its luma is at or above this level.
    highlight_level: int = 250
    # Fraction of blown highlights above which the photo is OVEREXPOSED (together with brightness).
    highlight_ratio: float = 0.10
