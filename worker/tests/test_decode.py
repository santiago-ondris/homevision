import struct
import zlib

import cv2
import numpy as np
import pytest

from vision.decode import InvalidImageError, decode
from vision.types import ImageLimits


def encode(image: np.ndarray, extension: str = ".png") -> bytes:
    success, encoded = cv2.imencode(extension, image)
    assert success
    return encoded.tobytes()


def test_png_preserves_bgr_pixels_and_dimensions() -> None:
    image = np.full((7, 9, 3), (10, 80, 200), dtype=np.uint8)
    original = image.copy()

    result = decode(encode(image), ImageLimits(9, 63))

    np.testing.assert_array_equal(result, original)
    assert result.dtype == np.uint8


def test_jpeg_decodes_to_three_byte_channels() -> None:
    image = np.full((7, 9, 3), 128, dtype=np.uint8)
    result = decode(encode(image, ".jpg"), ImageLimits(9, 63))

    assert result.shape == image.shape
    assert result.dtype == np.uint8


def test_greyscale_is_repeated_across_three_channels() -> None:
    image = np.array([[0, 90, 255]], dtype=np.uint8)
    result = decode(encode(image), ImageLimits(3, 3))

    np.testing.assert_array_equal(result, np.repeat(image[:, :, None], 3, axis=2))


def test_sixteen_bit_pixels_are_scaled_across_the_byte_range() -> None:
    image = np.array([[0, 32768, 65535]], dtype=np.uint16)
    result = decode(encode(image), ImageLimits(3, 3))

    np.testing.assert_array_equal(result[0, :, 0], [0, 128, 255])
    assert result.dtype == np.uint8
    assert result.shape == (1, 3, 3)


def test_alpha_is_blended_onto_white_including_partial_transparency() -> None:
    image = np.array([[[0, 0, 0, 0], [0, 0, 0, 128], [10, 80, 200, 255]]], dtype=np.uint8)
    result = decode(encode(image), ImageLimits(3, 3))

    np.testing.assert_array_equal(result, [[[255, 255, 255], [127, 127, 127], [10, 80, 200]]])


def test_sixteen_bit_alpha_is_scaled_and_flattened() -> None:
    image = np.array([[[0, 0, 0, 0], [0, 0, 0, 65535]]], dtype=np.uint16)
    result = decode(encode(image), ImageLimits(2, 2))

    np.testing.assert_array_equal(result, [[[255, 255, 255], [0, 0, 0]]])


@pytest.mark.parametrize("data", [b"", b"corrupt", b"\x89PNG\r\n\x1a\n"])
def test_empty_corrupt_and_truncated_bytes_raise_invalid_image(data: bytes) -> None:
    with pytest.raises(InvalidImageError):
        decode(data, ImageLimits(10000, 40000000))


@pytest.mark.parametrize("limits", [ImageLimits(8, 100), ImageLimits(10, 62)])
def test_decoded_dimensions_over_either_limit_are_rejected(limits: ImageLimits) -> None:
    image = np.full((7, 9, 3), 255, dtype=np.uint8)
    with pytest.raises(InvalidImageError):
        decode(encode(image), limits)


def test_twelve_thousand_pixel_side_is_rejected() -> None:
    image = np.full((1, 12000, 3), 255, dtype=np.uint8)
    with pytest.raises(InvalidImageError):
        decode(encode(image), ImageLimits(10000, 40000000))


def test_opencv_pixel_guard_rejects_oversized_header_before_pixel_allocation() -> None:
    header = struct.pack(">IIBBBBB", 10000, 10000, 8, 2, 0, 0, 0)

    def chunk(name: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + name
            + payload
            + struct.pack(">I", zlib.crc32(name + payload))
        )

    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
    data += chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b"")
    with pytest.raises(InvalidImageError) as caught:
        decode(data, ImageLimits(10000, 40000000))

    assert isinstance(caught.value.__cause__, cv2.error)
    assert "CV_IO_MAX_IMAGE_PIXELS" in str(caught.value.__cause__)


def test_jpeg_exif_orientation_does_not_rotate_the_pixel_grid() -> None:
    image = np.full((7, 9, 3), 128, dtype=np.uint8)
    encoded = encode(image, ".jpg")
    orientation_entry = struct.pack("<HHI", 274, 3, 1) + struct.pack("<H", 6) + b"\0\0"
    metadata = b"Exif\0\0II" + struct.pack("<HIH", 42, 8, 1)
    metadata += orientation_entry + struct.pack("<I", 0)
    tagged = encoded[:2] + b"\xff\xe1" + struct.pack(">H", len(metadata) + 2)
    tagged += metadata + encoded[2:]

    assert decode(tagged, ImageLimits(9, 63)).shape == image.shape
