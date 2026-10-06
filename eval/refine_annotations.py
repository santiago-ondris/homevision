"""Snap hand-drawn makesense.ai boxes to the printed checkbox border.

Reads   eval/ground_truth/raw/<sample>.csv  (label, x, y, width, height)
Writes  eval/ground_truth/<sample>.json  in the API's bbox format.

Only the four sides of each hand-drawn box move, and only by a few pixels.
Boxes are never added, removed or relabelled here.

bbox is [x1, y1, x2, y2] with x2/y2 exclusive, in original image pixels.
"""

import csv
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = {
    "sample1": "sample1.png",
    "sample2": "sample2.jpg",
    "sample3": "sample3.png",
    "sample4": "sample4.png",
}

INK_CONTRAST = 0.3  # ink is at least this far from paper towards the darkest pixel nearby
LINE_COVERAGE = 0.7  # share of the span that must be ink for a row/column to count as a border
FLANK = 6  # pixels checked past the box corners to tell a box side from a longer table rule
FLANK_COVERAGE = 0.6
MAX_BORDER = 7  # a run thicker than this is a table rule, not a checkbox side
CORNER_DEPTH = 4  # rows inward from a side where both perpendicular sides must be present
MERGED_BORDER = 3 # border thickness assumed when a side is merged into a rule
FAINT_DELTA = 14  # fallback threshold for very pale boxes: this much darker than paper


def ink_mask(gray, x0, y0, x1, y1, faint):
    patch = gray[y0:y1, x0:x1]
    paper = float(np.median(patch))
    if faint:
        return patch < paper - FAINT_DELTA
    darkest = float(np.percentile(patch, 2))
    return patch < paper - INK_CONTRAST * (paper - darkest)


def border_runs(ink, edge, reach, lo, hi):
    """Runs of consecutive rows near `edge` that are ink across columns lo..hi.

    Each run is (first_row, last_row, is_rule). A rule also covers the pixels
    just past both corners, which a checkbox side does not.
    """
    runs = []
    start = None
    last = min(ink.shape[0] - 1, edge + reach)
    for row in range(max(0, edge - reach), last + 2):
        covered = row <= last and ink[row, lo:hi].mean() >= LINE_COVERAGE
        if covered and start is None:
            start = row
        elif not covered and start is not None:
            left = ink[start:row, max(0, lo - FLANK - 3) : max(0, lo - 3)]
            right = ink[start:row, hi + 3 : hi + 3 + FLANK]
            is_rule = (
                left.size > 0
                and right.size > 0
                and left.mean() > FLANK_COVERAGE
                and right.mean() > FLANK_COVERAGE
            )
            runs.append((start, row - 1, is_rule))
            start = None
    return runs


def find_side(ink, edge, reach, lo, hi, outward):
    """Outer row of the checkbox side nearest to the hand-drawn `edge`, or None.

    `outward` is -1 for top/left and +1 for bottom/right. Callers pass a
    transposed mask for left/right.
    """
    runs = border_runs(ink, edge, reach, lo, hi)
    if not runs:
        return None

    def distance(run):
        return 0 if run[0] <= edge <= run[1] else min(abs(run[0] - edge), abs(run[1] - edge))

    def has_corners(run):
        # The box's own side has the two perpendicular sides running inward
        # from it. A neighbouring box's side, a few pixels away, does not.
        inner = run[1] if outward < 0 else run[0]
        a, b = sorted((inner - outward, inner - outward * CORNER_DEPTH))
        strip = ink[max(0, a) : b + 1]
        if strip.shape[0] < CORNER_DEPTH:
            return False
        near_lo = strip[:, max(0, lo - 6) : lo + 1].any(axis=1)
        near_hi = strip[:, hi - 1 : hi + 6].any(axis=1)
        return near_lo.all() and near_hi.all()

    sides = [r for r in runs if not r[2] and r[1] - r[0] < MAX_BORDER and has_corners(r)]
    if sides:
        first, last, _ = min(sides, key=distance)
        return first if outward < 0 else last
    # No free-standing side here: it is merged into a table rule.
    rules = [r for r in runs if has_corners(r)] or runs
    first, last, _ = min(rules, key=distance)
    inner = last if outward < 0 else first
    return inner + outward * (MERGED_BORDER - 1)


def snap(gray, x, y, w, h, faint=False):
    height, width = gray.shape
    reach = max(6, int(0.35 * min(w, h)))
    x0, y0 = max(0, x - reach - FLANK - 3), max(0, y - reach - FLANK - 3)
    x1, y1 = min(width, x + w + reach + FLANK + 3), min(height, y + h + reach + FLANK + 3)
    ink = ink_mask(gray, x0, y0, x1, y1, faint)

    left, top = x - x0, y - y0
    right, bottom = left + w - 1, top + h - 1
    for _ in range(2):
        found_left = find_side(ink.T, left, reach, top + 3, bottom - 2, -1)
        found_right = find_side(ink.T, right, reach, top + 3, bottom - 2, 1)
        if found_left is None or found_right is None:
            return None
        left, right = found_left, found_right
        found_top = find_side(ink, top, reach, left + 3, right - 2, -1)
        found_bottom = find_side(ink, bottom, reach, left + 3, right - 2, 1)
        if found_top is None or found_bottom is None:
            return None
        top, bottom = found_top, found_bottom
        reach = 4
    return left + x0, top + y0, right + x0 + 1, bottom + y0 + 1


def refine(sample):
    gray = np.asarray(
        Image.open(ROOT / "samples" / SAMPLES[sample]).convert("L"), dtype=np.float32
    )
    boxes, report = [], []
    with open(ROOT / "eval" / "ground_truth" / "raw" / f"{sample}.csv", newline="") as fh:
        for index, row in enumerate(csv.DictReader(fh)):
            x, y = int(row["bbox_x"]), int(row["bbox_y"])
            w, h = int(row["bbox_width"]), int(row["bbox_height"])
            drawn = (x, y, x + w, y + h)
            snapped = snap(gray, x, y, w, h) or snap(gray, x, y, w, h, faint=True)
            limit = max(6, int(0.35 * min(w, h)))
            if snapped and max(abs(a - b) for a, b in zip(snapped, drawn)) > limit:
                snapped = None
            label = row["label_name"]
            boxes.append(
                {
                    "bbox": list(snapped or drawn),
                    "is_checked": label.startswith("checked"),
                    "ambiguous": label.endswith("_ambiguous"),
                }
            )
            report.append({"index": index, "drawn": drawn, "snapped": snapped})
    return boxes, report


def main():
    out_dir = ROOT / "eval" / "ground_truth"
    out_dir.mkdir(parents=True, exist_ok=True)
    for sample, image in SAMPLES.items():
        boxes, report = refine(sample)
        payload = {"image": image, "boxes": boxes}
        (out_dir / f"{sample}.json").write_text(json.dumps(payload, indent=2) + "\n")
        kept = [r["index"] for r in report if r["snapped"] is None]
        print(f"{sample}: {len(boxes)} boxes, {len(kept)} left as drawn {kept}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
