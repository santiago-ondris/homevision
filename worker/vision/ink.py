from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray


def ink_mask(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    # Coloured print and tinted backgrounds are bright in some channel, so they read as paper.
    plane = image.max(axis=2)
    ink_value = int(np.iinfo(np.uint8).max)
    _, mask = cv2.threshold(plane, 0, ink_value, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return cast(NDArray[np.uint8], mask)
