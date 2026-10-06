import numpy as np
from numpy.typing import NDArray

from vision.params import Params
from vision.types import Box, Detection

MINIMUM_INSET = 2


def fill_ratio(ink: NDArray[np.uint8], box: Box, params: Params) -> float:
    horizontal_inset = max(MINIMUM_INSET, round(box.width * params.interior_inset))
    vertical_inset = max(MINIMUM_INSET, round(box.height * params.interior_inset))
    interior = ink[
        box.y1 + vertical_inset : box.y2 - vertical_inset,
        box.x1 + horizontal_inset : box.x2 - horizontal_inset,
    ]
    return float(np.mean(interior > 0))


def classify(ink: NDArray[np.uint8], box: Box, params: Params) -> Detection:
    ratio = fill_ratio(ink, box, params)
    return Detection(box, ratio > params.checked_threshold, ratio)
