from dataclasses import replace

import cv2
import numpy as np
import pytest

from vision.candidates import find_candidates, grow_to_border, plausible_shape
from vision.ink import ink_mask
from vision.params import Params
from vision.types import Box


def test_empty_box_is_found_with_exact_outer_coordinates() -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)
    original = image.copy()

    assert find_candidates(ink_mask(image), Params()) == [Box(20, 20, 50, 50)]
    np.testing.assert_array_equal(image, original)


def test_x_touching_the_border_does_not_split_the_box() -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)
    cv2.line(image, (20, 20), (49, 49), (0, 0, 0), 2)
    cv2.line(image, (20, 49), (49, 20), (0, 0, 0), 2)

    assert find_candidates(ink_mask(image), Params()) == [Box(20, 20, 50, 50)]


def test_box_top_on_a_long_horizontal_rule_is_found() -> None:
    image = np.full((80, 100, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)
    cv2.line(image, (0, 20), (99, 20), (0, 0, 0), 1)

    assert find_candidates(ink_mask(image), Params()) == [Box(20, 20, 50, 50)]


def test_boxes_with_three_pixels_of_paper_between_them_stay_separate() -> None:
    image = np.full((80, 100, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)
    cv2.rectangle(image, (53, 20), (82, 49), (0, 0, 0), 1)

    assert set(find_candidates(ink_mask(image), Params())) == {
        Box(20, 20, 50, 50),
        Box(53, 20, 83, 50),
    }


def test_thick_bold_letter_ring_is_not_a_checkbox() -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    cv2.circle(image, (35, 35), 12, (0, 0, 0), 6)

    assert find_candidates(ink_mask(image), Params()) == []


def test_mid_grey_box_on_white_is_found() -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (128, 128, 128), 1)

    assert find_candidates(ink_mask(image), Params()) == [Box(20, 20, 50, 50)]


def test_documented_contrast_limit_loses_near_paper_box_on_page_with_black_ink() -> None:
    image = np.full((100, 140, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)
    cv2.rectangle(image, (70, 20), (99, 49), (250, 250, 250), 1)
    cv2.rectangle(image, (20, 70), (99, 89), (0, 0, 0), -1)

    assert find_candidates(ink_mask(image), Params()) == [Box(20, 20, 50, 50)]


def test_near_paper_box_alone_is_found_by_the_page_relative_threshold() -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (250, 250, 250), 1)

    assert find_candidates(ink_mask(image), Params()) == [Box(20, 20, 50, 50)]


def test_blue_tinted_background_does_not_hide_a_black_box() -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    image[10:60, 10:60] = (255, 220, 220)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)

    assert find_candidates(ink_mask(image), Params()) == [Box(20, 20, 50, 50)]


def test_border_growth_stops_at_the_image_edges() -> None:
    strokes = np.full((20, 20), 255, dtype=np.uint8)

    assert grow_to_border(strokes, Box(2, 2, 18, 18), Params()) == Box(0, 0, 20, 20)


def test_border_growth_never_exceeds_the_configured_steps() -> None:
    strokes = np.full((40, 40), 255, dtype=np.uint8)

    assert grow_to_border(strokes, Box(10, 10, 30, 30), replace(Params(), max_border=2)) == Box(
        8, 8, 32, 32
    )


@pytest.mark.parametrize(
    "inner, outer",
    [
        (Box(1, 1, 10, 20), Box(0, 0, 11, 21)),
        (Box(1, 1, 120, 30), Box(0, 0, 121, 31)),
        (Box(1, 1, 19, 10), Box(0, 0, 20, 11)),
        (Box(1, 1, 30, 120), Box(0, 0, 31, 121)),
        (Box(1, 1, 19, 50), Box(0, 0, 20, 51)),
        (Box(1, 1, 59, 20), Box(0, 0, 60, 21)),
        (Box(6, 6, 24, 24), Box(0, 0, 30, 30)),
    ],
)
def test_shape_filter_rejects_invalid_sides_aspect_or_thick_border(inner: Box, outer: Box) -> None:
    assert not plausible_shape(inner, outer, Params())


def test_directional_extension_closes_short_corner_gaps() -> None:
    ink = np.zeros((80, 80), dtype=np.uint8)
    cv2.rectangle(ink, (20, 20), (49, 49), 255, 1)
    ink[20, 20:22] = 0
    ink[20:22, 20] = 0

    assert find_candidates(ink, Params()) == [Box(20, 20, 50, 50)]
    assert find_candidates(ink, replace(Params(), corner_gap=0)) == []
