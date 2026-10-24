import numpy as np
import pytest

from app.imaging import ImageDecodeError, PreparedImage, make_proxy, prepare_image
from tests.conftest import encode, sharp_image


def test_prepare_image_decodes_and_downsamples():
    image = prepare_image(encode(sharp_image(2000, 1000), ".png"), 1000)
    assert image.proxy.shape[:2] == (500, 1000)


def test_proxy_downsamples_wide_images():
    proxy = make_proxy(np.zeros((3000, 4000, 3), dtype=np.uint8), 1000)
    assert proxy.shape[:2] == (750, 1000)


def test_proxy_leaves_small_images_untouched():
    img = np.zeros((300, 400, 3), dtype=np.uint8)
    assert make_proxy(img, 1000) is img


def test_gray_is_computed_once():
    image = PreparedImage(np.zeros((10, 10, 3), dtype=np.uint8))
    assert image.gray.ndim == 2
    assert image.gray is image.gray


@pytest.mark.parametrize("data", [b"", b"not an image at all"])
def test_invalid_bytes_raise(data):
    with pytest.raises(ImageDecodeError):
        prepare_image(data, 1000)
