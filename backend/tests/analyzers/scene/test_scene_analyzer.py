from io import BytesIO

import cv2
import numpy as np
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from app.analyzers.scene import SceneAnalyzer
from app.imaging import PreparedImage, prepare_image, read_exif
from tests.conftest import encode, sharp_image, soft_background, solid_image


def analyze(img: np.ndarray, raw: bytes | None = None):
    return SceneAnalyzer().analyze(PreparedImage(img, raw=raw))


def concert_image(width: int = 800, height: int = 600) -> np.ndarray:
    """Mostly black frame with saturated colored light spots (stage lighting)."""
    img = np.full((height, width, 3), 8, dtype=np.uint8)
    rng = np.random.default_rng(1)
    for _ in range(40):
        x, y = int(rng.integers(0, width)), int(rng.integers(0, height // 2))
        color = [(255, 40, 200), (40, 80, 255), (30, 255, 120)][int(rng.integers(0, 3))]
        cv2.circle(img, (x, y), int(rng.integers(6, 18)), color, -1)
    return img


def camera_jpeg(**tags) -> bytes:
    """A small JPEG carrying EXIF camera settings, as a camera original would."""
    exif = Image.Exif()
    ifd = exif.get_ifd(0x8769)
    for tag, value in tags.items():
        ifd[int(tag, 16)] = value
    buf = BytesIO()
    Image.new("RGB", (64, 48), (120, 80, 40)).save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_flag_is_informational():
    result = analyze(sharp_image())
    assert result.flag == "OK" and result.score == 1.0


def test_concert_like_frame_is_dark_with_vivid_light():
    m = analyze(concert_image()).metrics
    assert m["dark_share"] > 0.5
    assert m["vivid_light"] >= 0.01


def test_plain_frames_have_no_vivid_light():
    assert analyze(solid_image(128, 800, 600)).metrics["vivid_light"] == 0.0
    assert analyze(solid_image(5, 800, 600)).metrics["dark_share"] == 1.0


def test_soft_texture_share_separates_soft_from_sharp():
    assert analyze(soft_background()).metrics["soft_texture_share"] > 0.5
    assert analyze(sharp_image()).metrics["soft_texture_share"] == 0.0


def test_exif_settings_become_metrics():
    raw = camera_jpeg(
        **{
            "0x829A": IFDRational(1, 2000),  # exposure time
            "0x829D": IFDRational(28, 10),  # f-number
            "0x8827": 6400,  # ISO
            "0xA405": 400,  # 35mm-equivalent focal length
            "0xA434": "EF 100mm f/2.8L Macro IS USM",
        }
    )
    m = analyze(sharp_image(), raw=raw).metrics
    assert m["exif_exposure_time"] == 0.0005
    assert m["exif_f_number"] == 2.8
    assert m["exif_iso"] == 6400
    assert m["exif_focal_length_35mm"] == 400
    assert m["exif_macro_lens"] == 1.0


def test_files_without_exif_report_no_exif_metrics():
    m = analyze(sharp_image(), raw=encode(sharp_image(), ".jpg")).metrics
    assert not any(k.startswith("exif_") for k in m)
    assert not any(k.startswith("exif_") for k in analyze(sharp_image()).metrics)  # no raw bytes


def test_read_exif_never_raises():
    assert read_exif(b"not an image") == {}
    assert read_exif(b"") == {}


def test_prepare_image_keeps_raw_bytes_for_exif():
    raw = camera_jpeg(**{"0x8827": 3200})
    assert prepare_image(raw, 1000).exif == {"iso": 3200.0}
