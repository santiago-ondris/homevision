import pytest

from eval.matching import iou, match_boxes
from vision.types import Box


@pytest.mark.parametrize(
    "first, second, expected",
    [
        (Box(0, 0, 10, 10), Box(0, 0, 10, 10), 1.0),
        (Box(0, 0, 10, 10), Box(20, 20, 30, 30), 0.0),
        (Box(0, 0, 10, 10), Box(10, 0, 20, 10), 0.0),
        (Box(0, 0, 10, 10), Box(2, 2, 7, 7), 0.25),
        (Box(0, 0, 0, 10), Box(0, 0, 10, 10), 0.0),
        (Box(0, 0, 10, 10), Box(5, 0, 3, 10), 0.0),
    ],
)
def test_iou_measures_area_with_exclusive_coordinates(
    first: Box, second: Box, expected: float
) -> None:
    assert iou(first, second) == expected


@pytest.mark.parametrize(
    "detected, annotated, threshold, expected",
    [
        ([Box(0, 0, 10, 10)], [Box(0, 0, 5, 10), Box(0, 0, 4, 10)], 0.5, [(0, 0)]),
        ([Box(0, 0, 10, 10)] * 2, [Box(0, 0, 10, 10)], 0.5, [(0, 0)]),
        ([Box(0, 0, 10, 10)], [Box(0, 0, 5, 10)], 0.5, [(0, 0)]),
        ([Box(0, 0, 10, 10)], [Box(0, 0, 5, 10)], 0.75, []),
        ([Box(0, 0, 10, 10)] * 2, [Box(0, 0, 10, 10)] * 2, 0.5, [(0, 0), (1, 1)]),
        (
            [Box(0, 0, 9, 10), Box(0, 0, 10, 10)],
            [Box(0, 0, 10, 10), Box(0, 0, 5, 10)],
            0.5,
            [(1, 0), (0, 1)],
        ),
        ([], [Box(0, 0, 10, 10)], 0.5, []),
        ([Box(0, 0, 10, 10)], [], 0.5, []),
    ],
)
def test_matching_is_greedy_one_to_one_with_stable_ties(
    detected: list[Box], annotated: list[Box], threshold: float, expected: list[tuple[int, int]]
) -> None:
    matches = match_boxes(detected, annotated, threshold)

    assert [(pair.detected_index, pair.annotated_index) for pair in matches] == expected
    assert [pair.iou for pair in matches] == [
        iou(detected[detected_index], annotated[annotated_index])
        for detected_index, annotated_index in expected
    ]
