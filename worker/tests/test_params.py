from dataclasses import FrozenInstanceError, asdict, replace

import pytest

from vision.params import Params


def test_default_parameters_preserve_the_measured_values() -> None:
    assert asdict(Params()) == {
        "line_length": 12,
        "corner_gap": 2,
        "rectangularity": 0.85,
        "max_border": 8,
        "min_side": 12,
        "max_side": 120,
        "min_aspect": 0.6,
        "max_aspect": 1.8,
        "min_interior": 0.7,
        "size_tolerance": 0.15,
        "interior_inset": 0.20,
        "checked_threshold": 0.08,
    }


@pytest.mark.parametrize("field", list(asdict(Params())))
def test_parameters_cannot_be_changed(field: str) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(Params(), field, 1)


def test_a_separate_parameter_instance_does_not_change_the_defaults() -> None:
    original = Params()
    changed = replace(original, line_length=20)

    assert changed.line_length == 20
    assert original.line_length == Params().line_length == 12
