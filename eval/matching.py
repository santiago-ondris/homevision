from collections.abc import Sequence
from dataclasses import dataclass

from vision.types import Box

DEFAULT_THRESHOLD = 0.5
STRICT_THRESHOLD = 0.75
THRESHOLDS = (DEFAULT_THRESHOLD, STRICT_THRESHOLD)


@dataclass(frozen=True)
class Match:
    detected_index: int
    annotated_index: int
    iou: float


def iou(first: Box, second: Box) -> float:
    if min(first.width, first.height, second.width, second.height) <= 0:
        return 0.0
    width = max(0, min(first.x2, second.x2) - max(first.x1, second.x1))
    height = max(0, min(first.y2, second.y2) - max(first.y1, second.y1))
    intersection = width * height
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union


def match_boxes(
    detected: Sequence[Box], annotated: Sequence[Box], threshold: float = DEFAULT_THRESHOLD
) -> tuple[Match, ...]:
    candidates = sorted(
        (
            Match(detected_index, annotated_index, iou(box, expected))
            for detected_index, box in enumerate(detected)
            for annotated_index, expected in enumerate(annotated)
        ),
        key=lambda pair: (-pair.iou, pair.detected_index, pair.annotated_index),
    )
    used_detections: set[int] = set()
    used_annotations: set[int] = set()
    matches = []
    for pair in candidates:
        if pair.iou < threshold:
            break
        if pair.detected_index in used_detections or pair.annotated_index in used_annotations:
            continue
        matches.append(pair)
        used_detections.add(pair.detected_index)
        used_annotations.add(pair.annotated_index)
    return tuple(matches)
