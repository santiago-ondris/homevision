import json
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
import pytest
from matching import match_boxes

from vision import pipeline
from vision.decode import decode
from vision.params import Params
from vision.pipeline import detect
from vision.types import Box, ImageLimits


@pytest.mark.parametrize("brightness, side", [(255, 80), (0, 80), (255, 1)])
def test_blank_black_and_single_pixel_images_return_no_detections(
    brightness: int, side: int
) -> None:
    image = np.full((side, side, 3), brightness, dtype=np.uint8)

    result = detect(image, Params())

    assert result.boxes == ()
    assert (result.width, result.height) == (side, side)


def test_single_box_with_border_touching_x_is_reported_checked() -> None:
    image = np.full((80, 80, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)
    cv2.line(image, (20, 20), (49, 49), (0, 0, 0), 2)
    cv2.line(image, (20, 49), (49, 20), (0, 0, 0), 2)
    original = image.copy()

    result = detect(image, Params())

    assert len(result.boxes) == 1
    assert result.boxes[0].bbox == Box(20, 20, 50, 50)
    assert result.boxes[0].is_checked
    np.testing.assert_array_equal(image, original)


def test_pipeline_sorts_by_row_then_column_and_removes_identical_boxes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boxes = [Box(50, 10, 80, 40), Box(10, 50, 40, 80), Box(10, 10, 40, 40)]
    monkeypatch.setattr(pipeline, "find_candidates", lambda ink, params: boxes + boxes[:1])

    result = detect(np.full((100, 100, 3), 255, dtype=np.uint8), Params())

    assert [detection.bbox for detection in result.boxes] == [boxes[2], boxes[0], boxes[1]]


def test_pipeline_reports_each_stage_duration_in_milliseconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamps = iter([0.0, 1.0, 3.0, 6.0, 10.0])
    monkeypatch.setattr(pipeline, "perf_counter", lambda: next(timestamps))

    result = detect(np.full((1, 1, 3), 255, dtype=np.uint8), Params())

    assert result.timings_ms == {
        "ink": 1000.0,
        "candidates": 2000.0,
        "sizing": 3000.0,
        "classify": 4000.0,
    }


@pytest.mark.parametrize(
    "filename, returned, matched, correct",
    [
        ("sample1.png", 119, 118, 118),
        ("sample2.jpg", 41, 41, 40),
        ("sample3.png", 48, 48, 48),
        ("sample4.png", 78, 78, 78),
    ],
)
def test_sample_regression_preserves_detection_and_classification_counts(
    filename: str, returned: int, matched: int, correct: int
) -> None:
    root = Path(__file__).resolve().parents[2]
    image = decode((root / "samples" / filename).read_bytes(), ImageLimits(10000, 40000000))
    truth_path = root / "eval" / "ground_truth" / f"{Path(filename).stem}.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8"))["boxes"]

    result = detect(image, Params())
    matches = match_boxes(
        [item.bbox for item in result.boxes], [Box(*row["bbox"]) for row in truth]
    )
    correct_count = sum(
        result.boxes[detected_index].is_checked == truth[truth_index]["is_checked"]
        for truth_index, detected_index in matches.items()
    )
    actual = (len(result.boxes), len(matches), correct_count)
    print(
        f"{filename}: returned={actual[0]}, matched={actual[1]}/{len(truth)}, correct={actual[2]}"
    )

    assert actual == (returned, matched, correct)


@pytest.mark.parametrize("filename", ["sample1.png", "sample2.jpg", "sample3.png", "sample4.png"])
def test_same_bytes_produce_byte_identical_boxes(filename: str) -> None:
    root = Path(__file__).resolve().parents[2]
    data = (root / "samples" / filename).read_bytes()
    limits = ImageLimits(10000, 40000000)
    params = Params()

    first = detect(decode(data, limits), params)
    second = detect(decode(data, limits), params)

    first_bytes = json.dumps([asdict(box) for box in first.boxes]).encode("utf-8")
    second_bytes = json.dumps([asdict(box) for box in second.boxes]).encode("utf-8")
    assert first_bytes == second_bytes


@pytest.mark.parametrize("kind", ["greyscale", "sixteen_bit", "transparent"])
def test_converted_png_images_run_through_the_pipeline_normally(kind: str) -> None:
    plane = np.full((80, 80), 255, dtype=np.uint8)
    cv2.rectangle(plane, (20, 20), (49, 49), 0, 1)
    if kind == "greyscale":
        image = plane
    elif kind == "sixteen_bit":
        image = plane.astype(np.uint16) * 257
    else:
        image = np.zeros((80, 80, 4), dtype=np.uint8)
        image[:, :, 3] = np.where(plane == 0, 255, 0)
    success, encoded = cv2.imencode(".png", image)
    assert success

    result = detect(decode(encoded.tobytes(), ImageLimits(10000, 40000000)), Params())

    assert len(result.boxes) == 1
    assert result.boxes[0].bbox == Box(20, 20, 50, 50)
    assert not result.boxes[0].is_checked
