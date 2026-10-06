from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from vision.params import Params
from vision.types import Box

MINIMUM_PAPER_SIDE = 4
MINIMUM_BORDER_MEAN = 128


def find_candidates(ink: NDArray[np.uint8], params: Params) -> list[Box]:
    horizontal = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, np.ones((1, params.line_length), dtype=np.uint8)
    )
    vertical = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, np.ones((params.line_length, 1), dtype=np.uint8)
    )
    strokes = cv2.bitwise_or(horizontal, vertical)
    reach = 2 * params.corner_gap + 1
    closed = cv2.bitwise_or(
        cv2.dilate(horizontal, np.ones((1, reach), dtype=np.uint8)),
        cv2.dilate(vertical, np.ones((reach, 1), dtype=np.uint8)),
    )
    return enclosed_regions(
        cast(NDArray[np.uint8], closed), cast(NDArray[np.uint8], strokes), params
    )


def enclosed_regions(
    closed: NDArray[np.uint8], strokes: NDArray[np.uint8], params: Params
) -> list[Box]:
    contours, hierarchy = cv2.findContours(closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    boxes = []
    for contour, relationship in zip(contours, hierarchy[0], strict=True):
        if relationship[3] < 0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        # Hole contours lie on ink, one pixel outside the enclosed paper.
        x, y, w, h = x + 1, y + 1, w - 2, h - 2
        if min(w, h) < MINIMUM_PAPER_SIDE:
            continue
        if cv2.contourArea(contour) < params.rectangularity * (w + 1) * (h + 1):
            continue
        inner = Box(x, y, x + w, y + h)
        outer = grow_to_border(strokes, inner, params)
        if plausible_shape(inner, outer, params):
            boxes.append(outer)
    return boxes


def grow_to_border(strokes: NDArray[np.uint8], inner: Box, params: Params) -> Box:
    height, width = strokes.shape
    x1, y1, x2, y2 = inner.x1, inner.y1, inner.x2, inner.y2
    for _ in range(params.max_border):
        if y1 == 0 or strokes[y1 - 1, x1:x2].mean() < MINIMUM_BORDER_MEAN:
            break
        y1 -= 1
    for _ in range(params.max_border):
        if y2 == height or strokes[y2, x1:x2].mean() < MINIMUM_BORDER_MEAN:
            break
        y2 += 1
    for _ in range(params.max_border):
        if x1 == 0 or strokes[y1:y2, x1 - 1].mean() < MINIMUM_BORDER_MEAN:
            break
        x1 -= 1
    for _ in range(params.max_border):
        if x2 == width or strokes[y1:y2, x2].mean() < MINIMUM_BORDER_MEAN:
            break
        x2 += 1
    return Box(x1, y1, x2, y2)


def plausible_shape(inner: Box, outer: Box, params: Params) -> bool:
    return (
        params.min_side <= outer.width <= params.max_side
        and params.min_side <= outer.height <= params.max_side
        and params.min_aspect <= outer.width / outer.height <= params.max_aspect
        and min(inner.width / outer.width, inner.height / outer.height) >= params.min_interior
    )
