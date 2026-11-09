from pydantic_settings import BaseSettings, SettingsConfigDict


class BlurSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PHOTOSORT_BLUR_", env_file=".env", extra="ignore")

    # Laplacian variance at or above which a tile (or, in the fallback, the whole image) is sharp.
    threshold: float = 80.0

    # Columns in the sharpness grid; rows follow the aspect ratio so tiles are roughly square.
    grid_cols: int = 12
    # Tiles whose intensity std dev is below this are flat (sky, plain wall) and ignored.
    min_tile_contrast: float = 6.0
    # Fraction of informative tiles that must be sharp for the whole photo to count as SHARP.
    sharp_area_ratio: float = 0.5
    # Smallest contiguous cluster of sharp tiles that counts as an in-focus subject.
    min_subject_tiles: int = 2
    # Subject must be at least this many times sharper than the background for SHALLOW_FOCUS.
    min_focus_ratio: float = 4.0
    # Light 3x3 Gaussian before the Laplacian so sensor noise / JPEG artifacts don't read as detail.
    denoise: bool = True
