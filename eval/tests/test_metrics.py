import pytest

from eval.matching import Match, match_boxes
from eval.metrics import Annotation, Counts, EvaluationInput, image_metrics, total_counts
from vision.types import Box, Detection


@pytest.mark.parametrize(
    "clear_only, expected_counts, expected_missed, expected_wrong",
    [
        (False, (5, 4, 3, 1), [3, 4], [1, 2]),
        (True, (3, 3, 2, 1), [3], [1]),
    ],
)
def test_metrics_count_matches_labels_and_errors_in_both_modes(
    clear_only: bool,
    expected_counts: tuple[int, int, int, int],
    expected_missed: list[int],
    expected_wrong: list[int],
) -> None:
    annotations = [
        Annotation(Box(i * 20, 0, i * 20 + 10, 10), False, i in (2, 4)) for i in range(5)
    ]
    detections = [Detection(item.bbox, i != 0, 0.2) for i, item in enumerate(annotations[:4])]
    matches = [Match(0, 0, 1.0), Match(1, 1, 0.8), Match(2, 2, 0.6)]

    result = image_metrics(EvaluationInput(annotations, detections, matches), clear_only)

    counts = result.counts
    assert (
        counts.annotated,
        counts.detected,
        counts.matched,
        counts.label_correct,
    ) == expected_counts
    assert counts.recall == pytest.approx(expected_counts[2] / expected_counts[0])
    assert counts.precision == pytest.approx(expected_counts[2] / expected_counts[1])
    assert counts.mean_iou == pytest.approx(0.9 if clear_only else 0.8)
    assert counts.label_accuracy == pytest.approx(expected_counts[3] / expected_counts[2])
    assert result.missed_annotations == tuple(annotations[i] for i in expected_missed)
    assert result.unmatched_detections == (detections[3],)
    assert [item.annotation for item in result.wrong_labels] == [
        annotations[i] for i in expected_wrong
    ]
    assert [item.detection for item in result.wrong_labels] == [
        detections[i] for i in expected_wrong
    ]


def test_clear_only_keeps_original_matches_instead_of_reassigning_detections() -> None:
    annotations = [
        Annotation(Box(0, 0, 10, 10), False, True),
        Annotation(Box(0, 0, 5, 10), False, False),
    ]
    detections = [Detection(Box(0, 0, 10, 10), False, 0.0)]
    matches = match_boxes([item.bbox for item in detections], [item.bbox for item in annotations])

    result = image_metrics(EvaluationInput(annotations, detections, matches), clear_only=True)

    assert result.counts == Counts(1, 0, 0, 0, 0.0)
    assert result.missed_annotations == (annotations[1],)
    assert result.unmatched_detections == ()
    assert result.matches == ()


@pytest.mark.parametrize("annotated, detected", [(0, 0), (1, 0), (0, 1)])
def test_missing_denominators_are_reported_as_unavailable(annotated: int, detected: int) -> None:
    annotation = Annotation(Box(0, 0, 10, 10), False, False)
    detection = Detection(Box(20, 0, 30, 10), False, 0.0)

    result = image_metrics(EvaluationInput([annotation] * annotated, [detection] * detected, []))

    assert result.counts.recall == (0.0 if annotated else None)
    assert result.counts.precision == (0.0 if detected else None)
    assert result.counts.mean_iou is None
    assert result.counts.label_accuracy is None


def test_totals_use_summed_counts_and_overlap_instead_of_mean_image_ratios() -> None:
    result = total_counts([Counts(1, 2, 1, 0, 0.5), Counts(9, 8, 8, 8, 8.0)])

    assert result == Counts(10, 10, 9, 8, 8.5)
    assert result.recall == 0.9
    assert result.precision == 0.9
    assert result.mean_iou == pytest.approx(8.5 / 9)
    assert result.label_accuracy == pytest.approx(8 / 9)
