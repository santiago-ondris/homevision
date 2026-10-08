from dataclasses import replace

import pytest

from vision.params import Params
from vision.sizing import typical_size_filter
from vision.types import Box


@pytest.mark.parametrize("count", [0, 1, 2])
def test_fewer_than_three_candidates_are_returned_unchanged(count: int) -> None:
    boxes = [Box(0, 0, 30, 30), Box(50, 0, 64, 14)][:count]

    assert typical_size_filter(boxes, Params()) == boxes


def test_ten_thirty_pixel_boxes_are_kept_and_three_fourteen_pixel_boxes_are_dropped() -> None:
    typical = [Box(x, 0, x + 30, 30) for x in range(0, 400, 40)]
    small = [Box(x, 50, x + 14, 64) for x in range(0, 60, 20)]
    boxes = small[:1] + typical + small[1:]
    original = boxes.copy()

    assert typical_size_filter(boxes, Params()) == typical
    assert boxes == original


def test_many_small_regions_lose_to_fewer_larger_boxes() -> None:
    small = [Box(x, 0, x + 14, 15) for x in range(0, 100, 20)]
    large = [Box(x, 50, x + 36, 86) for x in range(0, 120, 40)]

    assert typical_size_filter(small + large, Params()) == large


def test_equal_group_areas_favour_the_first_input_candidate() -> None:
    first = Box(0, 0, 20, 20)
    second = Box(30, 0, 50, 20)
    wide = Box(60, 0, 100, 20)

    assert typical_size_filter([first, second, wide], Params()) == [first, second]
    assert typical_size_filter([wide, first, second], Params()) == [wide]


def test_both_width_and_height_must_fall_within_the_relative_tolerance() -> None:
    square = Box(0, 0, 30, 30)
    close = Box(40, 0, 74, 34)
    tall = Box(80, 0, 110, 45)
    wide = Box(120, 0, 165, 30)

    assert typical_size_filter([square, close, tall, wide], Params()) == [square, close]


def test_relative_tolerance_is_measured_from_each_candidate() -> None:
    small = Box(0, 0, 100, 100)
    large = Box(150, 0, 265, 115)
    largest = Box(300, 0, 432, 132)

    assert typical_size_filter([small, large, largest], Params()) == [small, large, largest]


def test_tolerance_boundary_is_inclusive() -> None:
    base = Box(0, 0, 20, 20)
    edge = Box(30, 0, 47, 17)
    other = Box(60, 0, 70, 10)

    assert typical_size_filter([base, edge, other], Params()) == [base, edge]
    assert typical_size_filter([base, edge, other], replace(Params(), size_tolerance=0)) == [base]
