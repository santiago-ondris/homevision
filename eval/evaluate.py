import argparse
import json
from pathlib import Path

from eval import MAX_IMAGE_PIXELS
from eval.matching import THRESHOLDS, match_boxes
from eval.metrics import Annotation, EvaluationInput, image_metrics
from eval.report import (
    PRIMARY_COMBINATION,
    ImageReport,
    print_errors,
    print_table,
    write_json,
    write_overlay,
)
from vision.decode import decode
from vision.params import Params
from vision.pipeline import detect
from vision.types import Box, ImageLimits

ROOT = Path(__file__).resolve().parents[1]
IMAGE_LIMITS = ImageLimits(10000, MAX_IMAGE_PIXELS)
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})


def ground_truth_files(images: Path, annotations: Path) -> list[tuple[Path, Path]]:
    files = sorted(annotations.glob("*.json"))
    if not files:
        return []
    pairs = []
    annotated_images = set()
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        image = images / data["image"]
        if not image.is_file():
            raise FileNotFoundError(f"{file}: missing image {image}")
        pairs.append((image, file))
        annotated_images.add(image)
    for image in sorted(images.iterdir()):
        if (
            image.is_file()
            and image.suffix.lower() in IMAGE_SUFFIXES
            and image not in annotated_images
        ):
            raise FileNotFoundError(f"{image}: missing ground-truth file")
    return pairs


def evaluate_image(image_path: Path, annotation_path: Path, output: Path | None) -> ImageReport:
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    annotations = tuple(
        Annotation(Box(*item["bbox"]), item["is_checked"], item["ambiguous"])
        for item in data["boxes"]
    )
    image = decode(image_path.read_bytes(), IMAGE_LIMITS)
    detections = detect(image, Params()).boxes
    combinations = {}
    for threshold in THRESHOLDS:
        matches = match_boxes(
            [item.bbox for item in detections],
            [item.bbox for item in annotations],
            threshold,
        )
        for clear_only in (False, True):
            combinations[(threshold, clear_only)] = image_metrics(
                EvaluationInput(annotations, detections, matches), clear_only
            )
    result = ImageReport(image_path.name, annotations, detections, combinations)
    if output is not None:
        write_overlay(image, result, output / f"{image_path.name}.png")
    return result


def check_baseline(images: list[ImageReport], baseline_path: Path) -> bool:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    current = {image.image: image.combinations[PRIMARY_COMBINATION].counts for image in images}
    passed = True
    for image, expected in baseline.items():
        if image not in current:
            print(f"Baseline failed: {image} has no evaluation result")
            passed = False
            continue
        counts = current[image]
        actual = {
            "matched": counts.matched,
            "label_correct": counts.label_correct,
            "false_detections": counts.detected - counts.matched,
        }
        for name, value in actual.items():
            worse = value > expected[name] if name == "false_detections" else value < expected[name]
            if worse:
                print(f"Baseline failed: {image} {name}={value}, baseline={expected[name]}")
                passed = False
    return passed


def run(arguments: argparse.Namespace, root: Path) -> int:
    directories = {
        "samples": (root / "samples", root / "eval" / "ground_truth"),
        "holdout": (
            root / "eval" / "holdout" / "images",
            root / "eval" / "holdout" / "ground_truth",
        ),
    }
    selected = (
        directories if arguments.set == "all" else {arguments.set: directories[arguments.set]}
    )
    output = root / "eval" / "output"
    results = {}
    skipped = []
    for name, (images, annotations) in selected.items():
        pairs = ground_truth_files(images, annotations)
        if not pairs:
            skipped.append(name)
            continue
        overlays = output / "overlays" / name if arguments.overlays else None
        results[name] = [evaluate_image(image, annotation, overlays) for image, annotation in pairs]
        print_table(name, results[name])
    print_errors(results)
    for name in skipped:
        print(f"Skipping {name}: no ground-truth files")
    if arguments.report:
        write_json(results, output / "report.json")
    if arguments.check and not check_baseline(
        results.get("samples", []), root / "eval/baseline.json"
    ):
        return 1
    return 0


def main(arguments: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=("samples", "holdout", "all"), default="all")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--overlays", action="store_true")
    options = parser.parse_args(arguments)
    if options.check and options.set == "holdout":
        print("Usage error: --check requires samples; --set holdout cannot be used with --check")
        return 2
    try:
        return run(options, root)
    except (OSError, ValueError) as error:
        print(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
