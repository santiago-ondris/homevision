import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

from eval.matching import DEFAULT_THRESHOLD, STRICT_THRESHOLD, THRESHOLDS
from eval.metrics import Annotation, Counts, ImageMetrics, total_counts
from vision.types import Box, Detection

COMBINATIONS = tuple(
    (threshold, clear_only) for threshold in THRESHOLDS for clear_only in (False, True)
)
PRIMARY_COMBINATION = COMBINATIONS[0]
MATCHED_COLOR = (0, 255, 0)
MISSED_COLOR = (0, 0, 255)
UNMATCHED_COLOR = (255, 0, 255)
WRONG_LABEL_COLOR = (0, 165, 255)
OUTLINE_WIDTH = 2
PERCENT_SCALE = 100
ERROR_KIND_WIDTH = 18


@dataclass(frozen=True)
class ImageReport:
    image: str
    annotations: tuple[Annotation, ...]
    detections: tuple[Detection, ...]
    combinations: dict[tuple[float, bool], ImageMetrics]


def box_values(box: Box) -> list[int]:
    return [box.x1, box.y1, box.x2, box.y2]


def annotation_values(annotation: Annotation) -> dict[str, object]:
    return {
        "bbox": box_values(annotation.bbox),
        "is_checked": annotation.is_checked,
        "ambiguous": annotation.ambiguous,
    }


def detection_values(detection: Detection) -> dict[str, object]:
    return {
        "bbox": box_values(detection.bbox),
        "is_checked": detection.is_checked,
        "fill_ratio": round(detection.fill_ratio, 3),
    }


def counts_values(counts: Counts) -> dict[str, int | float | None]:
    return {
        "annotated": counts.annotated,
        "detected": counts.detected,
        "matched": counts.matched,
        "label_correct": counts.label_correct,
        "false_detections": counts.detected - counts.matched,
        "iou_sum": counts.iou_sum,
        "recall": counts.recall,
        "precision": counts.precision,
        "mean_iou": counts.mean_iou,
        "label_accuracy": counts.label_accuracy,
    }


def metrics_values(image: ImageReport, metrics: ImageMetrics) -> dict[str, object]:
    return {
        **counts_values(metrics.counts),
        "matches": [
            {
                "annotation": annotation_values(image.annotations[pair.annotated_index]),
                "detection": detection_values(image.detections[pair.detected_index]),
                "iou": pair.iou,
            }
            for pair in metrics.matches
        ],
        "missed_annotations": [annotation_values(item) for item in metrics.missed_annotations],
        "unmatched_detections": [detection_values(item) for item in metrics.unmatched_detections],
        "wrong_labels": [
            {
                "annotation": annotation_values(item.annotation),
                "detection": detection_values(item.detection),
                "iou": item.iou,
            }
            for item in metrics.wrong_labels
        ],
    }


def write_json(sets: dict[str, list[ImageReport]], output: Path) -> None:
    data = {
        name: [
            {
                "iou_threshold": threshold,
                "mode": "clear only" if clear_only else "all",
                "images": {
                    image.image: metrics_values(image, image.combinations[(threshold, clear_only)])
                    for image in images
                },
                "totals": counts_values(
                    total_counts(
                        [image.combinations[(threshold, clear_only)].counts for image in images]
                    )
                ),
            }
            for threshold, clear_only in COMBINATIONS
        ]
        for name, images in sets.items()
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def percentage(value: float | None) -> str:
    return "n/a" if value is None else f"{value * PERCENT_SCALE:.1f}%"


def table_row(name: str, counts: Counts) -> str:
    overlap = "n/a" if counts.mean_iou is None else f"{counts.mean_iou:.2f}"
    labels = "n/a" if counts.label_accuracy is None else f"{counts.label_correct}/{counts.matched}"
    return (
        f"{name:<14} {counts.annotated:>9} {counts.detected:>9} {counts.matched:>8} "
        f"{percentage(counts.recall):>7} {percentage(counts.precision):>10} "
        f"{overlap:>9} {labels:>9}"
    )


def print_table(name: str, images: list[ImageReport]) -> None:
    print(f"set: {name}   IoU >= {DEFAULT_THRESHOLD:.2f}   all boxes")
    print("image          annotated  detected  matched  recall  precision  mean IoU    labels")
    for image in images:
        print(table_row(image.image, image.combinations[PRIMARY_COMBINATION].counts))
    print(
        table_row(
            "total",
            total_counts([item.combinations[PRIMARY_COMBINATION].counts for item in images]),
        )
    )
    for combination in COMBINATIONS[1:]:
        threshold, clear_only = combination
        mode = "clear only" if clear_only else "all boxes"
        counts = total_counts([item.combinations[combination].counts for item in images])
        print(f"IoU >= {threshold:.2f}   {mode}")
        print(table_row("total", counts))
    print()


def label_text(is_checked: bool) -> str:
    return "checked" if is_checked else "unchecked"


def error_lines(metrics: ImageMetrics) -> list[str]:
    lines = []
    for annotation in metrics.missed_annotations:
        tag = "  (ambiguous)" if annotation.ambiguous else ""
        lines.append(
            f"  {'miss':<{ERROR_KIND_WIDTH}}{box_values(annotation.bbox)}  "
            f"{label_text(annotation.is_checked)}{tag}"
        )
    for detection in metrics.unmatched_detections:
        lines.append(
            f"  {'false detection':<{ERROR_KIND_WIDTH}}{box_values(detection.bbox)}  "
            f"{label_text(detection.is_checked)}"
        )
    for wrong in metrics.wrong_labels:
        tag = "  (ambiguous)" if wrong.annotation.ambiguous else ""
        lines.append(
            f"  {'wrong label':<{ERROR_KIND_WIDTH}}{box_values(wrong.detection.bbox)}  "
            f"detected {label_text(wrong.detection.is_checked)}, "
            f"annotated {label_text(wrong.annotation.is_checked)}{tag}"
        )
    return lines


def print_errors(sets: dict[str, list[ImageReport]]) -> None:
    extra_entries = []
    for images in sets.values():
        for image in images:
            primary = error_lines(image.combinations[PRIMARY_COMBINATION])
            if primary:
                print("\n".join([image.image, *primary]))
            strict = error_lines(image.combinations[(STRICT_THRESHOLD, False)])
            extra = [line for line in strict if line not in primary]
            if extra:
                extra_entries.append((image.image, extra))
    if extra_entries:
        print(f"only at IoU >= {STRICT_THRESHOLD:.2f}")
        for name, lines in extra_entries:
            print("\n".join([name, *lines]))


def draw_box(image: NDArray[np.uint8], box: Box, color: tuple[int, int, int]) -> None:
    cv2.rectangle(image, (box.x1, box.y1), (box.x2 - 1, box.y2 - 1), color, OUTLINE_WIDTH)


def write_overlay(image: NDArray[np.uint8], result: ImageReport, output: Path) -> None:
    overlay = image.copy()
    metrics = result.combinations[PRIMARY_COMBINATION]
    for pair in metrics.matches:
        draw_box(overlay, result.detections[pair.detected_index].bbox, MATCHED_COLOR)
    for annotation in metrics.missed_annotations:
        draw_box(overlay, annotation.bbox, MISSED_COLOR)
    for detection in metrics.unmatched_detections:
        draw_box(overlay, detection.bbox, UNMATCHED_COLOR)
    for wrong in metrics.wrong_labels:
        draw_box(overlay, wrong.detection.bbox, WRONG_LABEL_COLOR)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), overlay):
        raise OSError(f"Could not write overlay: {output}")
