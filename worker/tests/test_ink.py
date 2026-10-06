import numpy as np
import pytest

from vision.ink import ink_mask


def test_maximum_channel_keeps_coloured_pixels_as_paper() -> None:
    image = np.array(
        [[[0, 0, 0], [90, 90, 90], [255, 255, 255], [255, 0, 0], [255, 220, 220]]],
        dtype=np.uint8,
    )
    original = image.copy()

    result = ink_mask(image)

    np.testing.assert_array_equal(result, [[255, 255, 0, 0, 0]])
    np.testing.assert_array_equal(image, original)
    assert result.dtype == np.uint8


@pytest.mark.parametrize("brightness, expected", [(255, 0), (0, 255)])
def test_uniform_page_produces_a_uniform_mask(brightness: int, expected: int) -> None:
    image = np.full((30, 30, 3), brightness, dtype=np.uint8)

    assert np.all(ink_mask(image) == expected)


def test_single_pixel_image_produces_a_mask() -> None:
    image = np.full((1, 1, 3), 255, dtype=np.uint8)

    np.testing.assert_array_equal(ink_mask(image), [[0]])
