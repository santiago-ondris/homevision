import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from eval.matching import match_boxes
from eval.metrics import Annotation, EvaluationInput, image_metrics
from eval.report import (
    COMBINATIONS,
    ImageReport,
    print_errors,
    print_table,
    write_json,
    write_overlay,
)
from vision.types import Box, Detection


def error_report() -> ImageReport:
    annotations = tuple(Annotation(Box(x, 10, x + 10, 20), False, x == 50) for x in (10, 30, 50))
    detections = (
        Detection(annotations[0].bbox, False, 0.0),
        Detection(annotations[1].bbox, True, 0.2),
        Detection(Box(70, 10, 80, 20), False, 0.0),
    )
    combinations = {}
    for threshold, clear_only in COMBINATIONS:
        matches = match_boxes(
            [item.bbox for item in detections], [item.bbox for item in annotations], threshold
        )
        combinations[(threshold, clear_only)] = image_metrics(
            EvaluationInput(annotations, detections, matches), clear_only
        )
    return ImageReport("page.png", annotations, detections, combinations)


def test_json_and_stdout_include_each_error_with_its_boxes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = error_report()

    write_json({"samples": [result]}, tmp_path / "report.json")
    print_errors({"samples": [result]})

    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    counts = data["samples"][0]["images"]["page.png"]
    assert counts["missed_annotations"][0]["bbox"] == [50, 10, 60, 20]
    assert counts["unmatched_detections"][0]["bbox"] == [70, 10, 80, 20]
    assert counts["wrong_labels"][0]["annotation"]["is_checked"] is False
    assert counts["wrong_labels"][0]["detection"]["is_checked"] is True
    assert capsys.readouterr().out == (
        "page.png\n"
        "  miss              [50, 10, 60, 20]  unchecked  (ambiguous)\n"
        "  false detection   [70, 10, 80, 20]  unchecked\n"
        "  wrong label       [30, 10, 40, 20]  detected checked, annotated unchecked\n"
    )


def test_stricter_threshold_lists_only_additional_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    annotation = Annotation(Box(0, 0, 10, 10), True, False)
    detections = (
        Detection(Box(0, 0, 6, 10), True, 0.2),
        Detection(Box(20, 0, 30, 10), False, 0.0),
    )
    combinations = {}
    for threshold, clear_only in COMBINATIONS:
        matches = match_boxes([item.bbox for item in detections], [annotation.bbox], threshold)
        combinations[(threshold, clear_only)] = image_metrics(
            EvaluationInput((annotation,), detections, matches), clear_only
        )
    result = ImageReport("page.png", (annotation,), detections, combinations)

    print_errors({"samples": [result]})

    assert capsys.readouterr().out == (
        "page.png\n"
        "  false detection   [20, 0, 30, 10]  unchecked\n"
        "only at IoU >= 0.75\n"
        "page.png\n"
        "  miss              [0, 0, 10, 10]  checked\n"
        "  false detection   [0, 0, 6, 10]  checked\n"
    )


def test_zero_denominators_render_as_na_and_json_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    metrics = image_metrics(EvaluationInput((), (), ()))
    result = ImageReport("blank.png", (), (), dict.fromkeys(COMBINATIONS, metrics))

    print_table("samples", [result])
    write_json({"samples": [result]}, tmp_path / "report.json")

    assert "n/a" in capsys.readouterr().out
    data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    for combination in data["samples"]:
        for name in ("recall", "precision", "mean_iou", "label_accuracy"):
            assert combination["totals"][name] is None
            assert combination["images"]["blank.png"][name] is None


def test_overlay_colors_distinguish_matches_misses_false_detections_and_wrong_labels(
    tmp_path: Path,
) -> None:
    image = np.full((30, 90, 3), 255, dtype=np.uint8)
    original = image.copy()

    write_overlay(image, error_report(), tmp_path / "overlay.png")

    overlay = cv2.imread(str(tmp_path / "overlay.png"))
    assert overlay is not None
    for x, color in [
        (10, (0, 255, 0)),
        (30, (0, 165, 255)),
        (50, (0, 0, 255)),
        (70, (255, 0, 255)),
    ]:
        assert tuple(overlay[10, x]) == color
    np.testing.assert_array_equal(image, original)
