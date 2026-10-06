from collections.abc import Sequence
from dataclasses import dataclass

from eval.matching import Match
from vision.types import Box, Detection


@dataclass(frozen=True)
class Annotation:
    bbox: Box
    is_checked: bool
    ambiguous: bool


@dataclass(frozen=True)
class Counts:
    annotated: int
    detected: int
    matched: int
    label_correct: int
    iou_sum: float

    @property
    def recall(self) -> float | None:
        return ratio(self.matched, self.annotated)

    @property
    def precision(self) -> float | None:
        return ratio(self.matched, self.detected)

    @property
    def mean_iou(self) -> float | None:
        return ratio(self.iou_sum, self.matched)

    @property
    def label_accuracy(self) -> float | None:
        return ratio(self.label_correct, self.matched)


@dataclass(frozen=True)
class WrongLabel:
    annotation: Annotation
    detection: Detection
    iou: float


@dataclass(frozen=True)
class ImageMetrics:
    counts: Counts
    matches: tuple[Match, ...]
    missed_annotations: tuple[Annotation, ...]
    unmatched_detections: tuple[Detection, ...]
    wrong_labels: tuple[WrongLabel, ...]


@dataclass(frozen=True)
class EvaluationInput:
    annotations: Sequence[Annotation]
    detections: Sequence[Detection]
    matches: Sequence[Match]


def ratio(numerator: float, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def image_metrics(data: EvaluationInput, clear_only: bool = False) -> ImageMetrics:
    annotations = {
        i: annotation
        for i, annotation in enumerate(data.annotations)
        if not clear_only or not annotation.ambiguous
    }
    excluded_detections = {
        pair.detected_index
        for pair in data.matches
        if clear_only and data.annotations[pair.annotated_index].ambiguous
    }
    detections = {
        i: detection for i, detection in enumerate(data.detections) if i not in excluded_detections
    }
    matches = tuple(pair for pair in data.matches if pair.annotated_index in annotations)
    matched_annotations = {pair.annotated_index for pair in matches}
    matched_detections = {pair.detected_index for pair in matches}
    wrong_labels = tuple(
        WrongLabel(annotations[pair.annotated_index], detections[pair.detected_index], pair.iou)
        for pair in matches
        if annotations[pair.annotated_index].is_checked
        != detections[pair.detected_index].is_checked
    )
    counts = Counts(
        len(annotations),
        len(detections),
        len(matches),
        len(matches) - len(wrong_labels),
        sum(pair.iou for pair in matches),
    )
    return ImageMetrics(
        counts,
        matches,
        tuple(annotation for i, annotation in annotations.items() if i not in matched_annotations),
        tuple(detection for i, detection in detections.items() if i not in matched_detections),
        wrong_labels,
    )


def total_counts(counts: Sequence[Counts]) -> Counts:
    return Counts(
        sum(item.annotated for item in counts),
        sum(item.detected for item in counts),
        sum(item.matched for item in counts),
        sum(item.label_correct for item in counts),
        sum(item.iou_sum for item in counts),
    )
