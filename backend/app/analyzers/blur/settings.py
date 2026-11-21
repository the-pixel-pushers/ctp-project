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
    sharp_area_ratio: float = 0.40
    # Smallest contiguous cluster of sharp tiles that counts as an in-focus subject.
    min_subject_tiles: int = 2
    # Exception to `min_subject_tiles`: when exactly one tile in the whole frame is sharp, it still counts
    # as the subject if it stands out at least this strongly (a very soft, clean rest of the frame).
    min_single_tile_focus_ratio: float = 40.0
    # For SHALLOW_FOCUS the largest sharp cluster must hold at least this share of ALL sharp tiles.
    # A real subject is one blob; scattered specks (noise, JPEG artifacts) on a soft frame are not.
    min_subject_cluster_share: float = 0.5
    # Exception to the share rule: a largest cluster of at least this many tiles is a real subject even
    # when other sharp tiles are scattered elsewhere (smooth skin/clothing fragments a real subject).
    confident_subject_tiles: int = 5
    # Subject must be at least this many times sharper than the background for SHALLOW_FOCUS.
    # Deliberate shallow focus has a very soft background, so the bar is high; soft frames whose
    # "best" region is only moderately sharper than the rest fall below it.
    min_focus_ratio: float = 20.0
    # The SHALLOW_FOCUS subject must also be sharp in absolute terms (mean tile Laplacian variance).
    # A coarse guard only: keep it well below real in-focus subjects (~125-140 in the samples).
    min_shallow_subject_sharpness: float = 100.0
    # Light 3x3 Gaussian before the Laplacian so sensor noise / JPEG artifacts don't read as detail.
    denoise: bool = True
