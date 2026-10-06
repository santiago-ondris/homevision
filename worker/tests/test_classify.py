from dataclasses import replace

import cv2
import numpy as np
import pytest

from vision.classify import classify, fill_ratio
from vision.params import Params
from vision.types import Box


def test_empty_box_has_no_interior_ink_and_is_not_checked() -> None:
    ink = np.zeros((80, 80), dtype=np.uint8)
    cv2.rectangle(ink, (20, 20), (49, 49), 255, 1)
    box = Box(20, 20, 50, 50)

    assert fill_ratio(ink, box, Params()) == 0.0
    assert not classify(ink, box, Params()).is_checked


@pytest.mark.parametrize("mark", ["x", "tick"])
def test_x_and_tick_have_interior_ink_above_the_checked_threshold(mark: str) -> None:
    ink = np.zeros((80, 80), dtype=np.uint8)
    cv2.rectangle(ink, (20, 20), (49, 49), 255, 1)
    if mark == "x":
        cv2.line(ink, (20, 20), (49, 49), 255, 2)
        cv2.line(ink, (20, 49), (49, 20), 255, 2)
    else:
        cv2.line(ink, (26, 33), (32, 42), 255, 2)
        cv2.line(ink, (32, 42), (46, 24), 255, 2)
    original = ink.copy()

    result = classify(ink, Box(20, 20, 50, 50), Params())

    assert result.is_checked
    assert Params().checked_threshold < result.fill_ratio <= 1.0
    np.testing.assert_array_equal(ink, original)


def test_ratio_equal_to_the_threshold_is_not_checked() -> None:
    ink = np.zeros((16, 16), dtype=np.uint8)
    ink[3, 3:11] = 255
    box = Box(0, 0, 16, 16)

    assert fill_ratio(ink, box, Params()) == 0.08
    assert not classify(ink, box, Params()).is_checked
    ink[4, 3] = 255
    assert classify(ink, box, Params()).is_checked


def test_fully_inked_interior_has_ratio_one() -> None:
    ink = np.full((30, 30), 255, dtype=np.uint8)

    assert fill_ratio(ink, Box(0, 0, 30, 30), Params()) == 1.0


def test_insets_are_rounded_separately_for_width_and_height() -> None:
    ink = np.zeros((18, 28), dtype=np.uint8)
    ink[4:14, 6:22] = 255

    assert fill_ratio(ink, Box(0, 0, 28, 18), Params()) == 1.0


def test_inset_never_drops_below_two_pixels() -> None:
    ink = np.zeros((12, 12), dtype=np.uint8)
    ink[2:10, 2:10] = 255

    assert fill_ratio(ink, Box(0, 0, 12, 12), replace(Params(), interior_inset=0)) == 1.0


def test_rounding_of_half_pixel_inset_uses_round() -> None:
    ink = np.zeros((25, 25), dtype=np.uint8)
    ink[2:23, 2:23] = 255

    assert fill_ratio(ink, Box(0, 0, 25, 25), replace(Params(), interior_inset=0.1)) == 1.0
