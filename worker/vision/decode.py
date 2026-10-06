from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from vision.types import ImageLimits


class InvalidImageError(ValueError):
    pass


def decode(data: bytes, limits: ImageLimits) -> NDArray[np.uint8]:
    if not data:
        raise InvalidImageError("The image is empty.")
    try:
        image = cv2.imdecode(
            np.frombuffer(data, dtype=np.uint8),
            cv2.IMREAD_UNCHANGED | cv2.IMREAD_IGNORE_ORIENTATION,
        )
    except cv2.error as error:
        raise InvalidImageError("The image could not be decoded.") from error
    if image is None or image.size == 0:
        raise InvalidImageError("The image could not be decoded.")
    height, width = image.shape[:2]
    if max(width, height) > limits.max_side or width * height > limits.max_pixels:
        raise InvalidImageError("The image dimensions exceed the allowed limits.")
    if image.dtype == np.uint16:
        maximum_byte = np.iinfo(np.uint8).max
        maximum_word = np.iinfo(np.uint16).max
        image = np.rint(image.astype(np.float64) * maximum_byte / maximum_word).astype(np.uint8)
    if image.ndim == 2:
        return cast(NDArray[np.uint8], cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
    if image.shape[2] == 4:
        white = float(np.iinfo(np.uint8).max)
        alpha = image[:, :, 3:4].astype(np.float64) / white
        return np.rint(image[:, :, :3] * alpha + white * (1 - alpha)).astype(np.uint8)
    return cast(NDArray[np.uint8], image)
