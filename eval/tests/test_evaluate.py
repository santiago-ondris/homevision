import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from eval import evaluate
from eval.evaluate import main
from vision.types import Box, Detection, DetectionResult


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    images = tmp_path / "samples"
    annotations = tmp_path / "eval" / "ground_truth"
    images.mkdir()
    annotations.mkdir(parents=True)
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (49, 49), (0, 0, 0), 1)
    assert cv2.imwrite(str(images / "page.png"), image)
    (annotations / "page.json").write_text(
        json.dumps(
            {
                "image": "page.png",
                "boxes": [{"bbox": [20, 20, 50, 50], "is_checked": False, "ambiguous": False}],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "eval" / "baseline.json").write_text(
        json.dumps({"page.png": {"matched": 1, "label_correct": 1, "false_detections": 0}}),
        encoding="utf-8",
    )
    return tmp_path


def test_check_passes_at_baseline_and_writes_all_combinations_and_overlays(
    dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--check", "--report", "--overlays"], dataset) == 0

    output = capsys.readouterr().out
    assert "Skipping holdout: no ground-truth files" in output
    assert "100.0%" in output
    report = json.loads((dataset / "eval/output/report.json").read_text(encoding="utf-8"))
    assert [(item["iou_threshold"], item["mode"]) for item in report["samples"]] == [
        (0.5, "all"),
        (0.5, "clear only"),
        (0.75, "all"),
        (0.75, "clear only"),
    ]
    for combination in report["samples"]:
        counts = combination["images"]["page.png"]
        assert (counts["annotated"], counts["detected"], counts["matched"]) == (1, 1, 1)
        assert counts["label_correct"] == 1
        assert counts["mean_iou"] == 1.0
        assert counts["missed_annotations"] == []
        assert counts["unmatched_detections"] == []
        assert counts["wrong_labels"] == []
        assert counts["matches"][0]["detection"]["bbox"] == [20, 20, 50, 50]
        assert combination["totals"]["label_accuracy"] == 1.0
    assert (dataset / "eval/output/overlays/samples/page.png.png").is_file()


@pytest.mark.parametrize(
    "flags", [[], ["--check"], ["--report"], ["--overlays"], ["--report", "--overlays"]]
)
def test_output_files_are_created_only_for_the_requested_flags(
    dataset: Path, capsys: pytest.CaptureFixture[str], flags: list[str]
) -> None:
    assert main(flags, dataset) == 0

    output = dataset / "eval/output"
    assert output.exists() == ("--report" in flags or "--overlays" in flags)
    assert (output / "report.json").exists() == ("--report" in flags)
    assert (output / "overlays/samples/page.png.png").exists() == ("--overlays" in flags)
    assert "page.png" in capsys.readouterr().out


@pytest.mark.parametrize(
    "case",
    [
        ((), "matched"),
        ((Detection(Box(20, 20, 50, 50), True, 0.2),), "label_correct"),
        (
            (
                Detection(Box(20, 20, 50, 50), False, 0.0),
                Detection(Box(60, 60, 90, 90), False, 0.0),
            ),
            "false_detections",
        ),
    ],
)
def test_check_fails_when_a_detector_count_regresses(
    dataset: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: tuple[tuple[Detection, ...], str],
) -> None:
    detections, failed_count = case
    monkeypatch.setattr(
        evaluate, "detect", lambda image, params: DetectionResult(100, 100, detections, {})
    )

    assert main(["--set", "samples", "--check"], dataset) == 1
    assert f"page.png {failed_count}=" in capsys.readouterr().out
    assert main(["--set", "samples"], dataset) == 0


def test_holdout_check_is_a_usage_error_before_reading_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--set", "holdout", "--check"], tmp_path) == 2

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert "--check" in lines[0] and "--set holdout" in lines[0]
    assert not (tmp_path / "eval/output").exists()


def test_skipped_set_notice_follows_the_failure_list(
    dataset: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(evaluate, "detect", lambda image, params: DetectionResult(100, 100, (), {}))

    assert main([], dataset) == 0

    output = capsys.readouterr().out
    assert output.endswith(
        "page.png\n"
        "  miss              [20, 20, 50, 50]  unchecked\n"
        "Skipping holdout: no ground-truth files\n"
    )


@pytest.mark.parametrize("missing", ["image", "annotation"])
def test_missing_image_or_annotation_names_the_file_and_exits_two(
    dataset: Path, capsys: pytest.CaptureFixture[str], missing: str
) -> None:
    if missing == "image":
        (dataset / "samples/page.png").unlink()
    else:
        image = np.full((10, 10, 3), 255, dtype=np.uint8)
        assert cv2.imwrite(str(dataset / "samples/unannotated.png"), image)

    assert main(["--set", "samples"], dataset) == 2
    message = capsys.readouterr().out
    assert ("page.png" if missing == "image" else "unannotated.png") in message
    assert "missing" in message


def test_set_without_annotations_is_skipped_even_if_it_contains_images(
    dataset: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (dataset / "eval/ground_truth/page.json").unlink()

    assert main(["--set", "samples"], dataset) == 0
    assert capsys.readouterr().out.strip() == "Skipping samples: no ground-truth files"
