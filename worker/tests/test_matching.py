import pytest
from matching import intersection_over_union, match_boxes

from vision.types import Box


@pytest.mark.parametrize(
    "second, expected",
    [(Box(0, 0, 10, 10), 1.0), (Box(10, 0, 20, 10), 0.0), (Box(0, 0, 5, 10), 0.5)],
)
def test_overlap_uses_exclusive_coordinates(second: Box, expected: float) -> None:
    assert intersection_over_union(Box(0, 0, 10, 10), second) == expected


def test_matching_is_one_to_one_and_accepts_exactly_half_overlap() -> None:
    detected = [Box(0, 0, 10, 10)]
    truth = [Box(0, 0, 5, 10), Box(0, 0, 4, 10)]

    assert match_boxes(detected, truth) == {0: 0}


def test_each_truth_box_can_only_use_one_detection() -> None:
    box = Box(0, 0, 10, 10)
    matched = match_boxes([box, box], [box])

    assert len(matched) == 1


def test_matching_takes_highest_overlap_before_other_pairs() -> None:
    detected = [Box(0, 0, 10, 10), Box(0, 0, 9, 10)]
    truth = [Box(0, 0, 10, 10), Box(0, 0, 5, 10)]

    assert match_boxes(detected, truth) == {0: 0, 1: 1}


def test_empty_inputs_have_no_matches() -> None:
    assert match_boxes([], []) == {}
