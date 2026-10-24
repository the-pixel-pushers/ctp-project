from pydantic_settings import BaseSettings, SettingsConfigDict


class BlurSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHOTOSORT_BLUR_", env_file=".env", extra="ignore")

    threshold: float = 80.0
