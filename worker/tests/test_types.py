from dataclasses import FrozenInstanceError

import pytest

from vision.types import Box, ImageLimits


def test_box_dimensions_use_exclusive_bottom_right_coordinates() -> None:
    box = Box(10, 20, 40, 65)

    assert box.width == 30
    assert box.height == 45
    assert Box(0, 0, 1, 1).width == 1
    assert Box(0, 0, 1, 1).height == 1


def test_box_coordinates_cannot_be_changed() -> None:
    box = Box(10, 20, 40, 65)

    with pytest.raises(FrozenInstanceError):
        box.x1 = 11


def test_identical_boxes_are_equal_and_deduplicate_by_value() -> None:
    box = Box(10, 20, 40, 65)

    assert {box, Box(10, 20, 40, 65), Box(11, 20, 40, 65)} == {box, Box(11, 20, 40, 65)}


@pytest.mark.parametrize("field", ["max_side", "max_pixels"])
def test_image_limits_cannot_be_changed(field: str) -> None:
    limits = ImageLimits(max_side=10000, max_pixels=40000000)

    with pytest.raises(FrozenInstanceError):
        setattr(limits, field, 1)
