"""Experiment 2: three ways of finding checkbox candidates, scored on the ground truth.

    components  ink blobs that look like a small rectangle
    holes       enclosed paper regions (the inside of a box) in the ink mask
    lines       same as holes, but on a mask that keeps only horizontal and
                vertical strokes, so marks drawn inside a box do not split it

Every method gets the same loose shape filter. The typical-size filter is
experiment 3 and is reported separately here.
"""

import sys

import cv2
import numpy as np

from common import OUT, SAMPLES, load_image, load_truth

MIN_SIDE, MAX_SIDE = 12, 120
MIN_ASPECT, MAX_ASPECT = 0.6, 1.8
RECTANGULARITY = 0.85  # region area / bounding box area
LINE_LENGTH = 12  # shortest straight stroke kept by the `lines` mask
MAX_BORDER = 8
CORNER_GAP = 2  # pixels a stroke is extended at each end to close open corners
MIN_INTERIOR = 0.7  # interior side / outer side
IOU_MATCH = 0.5
SIZE_TOLERANCE = 0.15


def ink_mask(image):
    plane = image.max(axis=2)
    _, mask = cv2.threshold(plane, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return mask


def plausible(w, h):
    return MIN_SIDE <= w <= MAX_SIDE and MIN_SIDE <= h <= MAX_SIDE and MIN_ASPECT <= w / h <= MAX_ASPECT


def by_components(ink):
    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    boxes = []
    for x, y, w, h, _ in stats[1:count]:
        if plausible(w, h):
            boxes.append((x, y, x + w, y + h))
    return boxes


def grow_to_border(mask, x1, y1, x2, y2):
    """Extend an interior region outward over the printed border around it."""
    height, width = mask.shape
    for _ in range(MAX_BORDER):
        if y1 == 0 or mask[y1 - 1, x1:x2].mean() < 128:
            break
        y1 -= 1
    for _ in range(MAX_BORDER):
        if y2 == height or mask[y2, x1:x2].mean() < 128:
            break
        y2 += 1
    for _ in range(MAX_BORDER):
        if x1 == 0 or mask[y1:y2, x1 - 1].mean() < 128:
            break
        x1 -= 1
    for _ in range(MAX_BORDER):
        if x2 == width or mask[y1:y2, x2].mean() < 128:
            break
        x2 += 1
    return x1, y1, x2, y2


def enclosed_regions(closed, border, thin_only):
    """Paper regions fully surrounded by `closed`, returned as outer boxes.

    Holes come from the contour hierarchy, so ink left inside a region (what
    remains of a mark) does not count against its rectangularity. The outer
    box is measured on `border`, the mask before any gap closing.
    """
    contours, hierarchy = cv2.findContours(closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    if hierarchy is None:
        return boxes
    for contour, (_, _, _, parent) in zip(contours, hierarchy[0]):
        if parent < 0:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        # a hole contour runs on the surrounding ink, one pixel outside the paper
        x, y, w, h = x + 1, y + 1, w - 2, h - 2
        if w < 4 or h < 4 or cv2.contourArea(contour) < RECTANGULARITY * (w + 1) * (h + 1):
            continue
        x1, y1, x2, y2 = grow_to_border(border, x, y, x + w, y + h)
        if not plausible(x2 - x1, y2 - y1):
            continue
        # a checkbox is mostly interior; a letter such as 'o' or 'P' is mostly stroke
        if thin_only and min(w / (x2 - x1), h / (y2 - y1)) < MIN_INTERIOR:
            continue
        boxes.append((x1, y1, x2, y2))
    return boxes


def by_holes(ink):
    return enclosed_regions(ink, ink, thin_only=False)


def straight_strokes(ink):
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, LINE_LENGTH), np.uint8))
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((LINE_LENGTH, 1), np.uint8))
    return horizontal, vertical


def by_lines(ink):
    horizontal, vertical = straight_strokes(ink)
    strokes = cv2.bitwise_or(horizontal, vertical)
    # Thin or greyish borders lose a pixel or two where two sides meet. Extend each
    # stroke along its own direction only, so parallel rules nearby do not merge.
    reach = 2 * CORNER_GAP + 1
    closed = cv2.bitwise_or(
        cv2.dilate(horizontal, np.ones((1, reach), np.uint8)),
        cv2.dilate(vertical, np.ones((reach, 1), np.uint8)),
    )
    return enclosed_regions(closed, strokes, thin_only=True)


METHODS = {"components": by_components, "holes": by_holes, "lines": by_lines}


def typical_size_filter(boxes):
    """Keep boxes close to the most common size among the candidates."""
    if len(boxes) < 3:
        return boxes
    sizes = np.array([(x2 - x1, y2 - y1) for x1, y1, x2, y2 in boxes], dtype=float)
    best_members = None
    for w, h in sizes:
        members = (np.abs(sizes[:, 0] - w) <= SIZE_TOLERANCE * w) & (
            np.abs(sizes[:, 1] - h) <= SIZE_TOLERANCE * h
        )
        if best_members is None or members.sum() > best_members.sum():
            best_members = members
    return [b for b, keep in zip(boxes, best_members) if keep]


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def match(detected, truth):
    """Greedy one-to-one matching by IoU. Returns {truth index: detected index}."""
    pairs = sorted(
        ((iou(d, t["bbox"]), di, ti) for di, d in enumerate(detected) for ti, t in enumerate(truth)),
        reverse=True,
    )
    matched, used = {}, set()
    for score, di, ti in pairs:
        if score < IOU_MATCH:
            break
        if ti not in matched and di not in used:
            matched[ti] = di
            used.add(di)
    return matched


def score(detected, truth):
    matched = match(detected, truth)
    checked = [i for i, t in enumerate(truth) if t["is_checked"]]
    empty = [i for i, t in enumerate(truth) if not t["is_checked"]]
    return {
        "found": len(matched),
        "truth": len(truth),
        "detected": len(detected),
        "checked_found": sum(i in matched for i in checked),
        "checked": len(checked),
        "empty_found": sum(i in matched for i in empty),
        "empty": len(empty),
        "mean_iou": float(np.mean([iou(detected[d], truth[t]["bbox"]) for t, d in matched.items()]))
        if matched
        else 0.0,
        "matched": matched,
    }


def draw(image, detected, truth, matched, path):
    canvas = image.copy()
    hit = set(matched.values())
    for i, t in enumerate(truth):
        if i not in matched:
            x1, y1, x2, y2 = t["bbox"]
            cv2.rectangle(canvas, (x1 - 4, y1 - 4), (x2 + 3, y2 + 3), (0, 0, 255), 3)
    for i, (x1, y1, x2, y2) in enumerate(detected):
        colour = (0, 170, 0) if i in hit else (255, 0, 255)
        cv2.rectangle(canvas, (int(x1), int(y1)), (int(x2) - 1, int(y2) - 1), colour, 2)
    cv2.imwrite(str(path), canvas)


def main():
    header = f"{'method':11} {'filter':6} {'sample':8} {'recall':>9} {'checked':>8} {'empty':>8} {'precision':>10} {'IoU':>5}"
    print(header)
    for name, method in METHODS.items():
        for filtered in (False, True):
            totals = np.zeros(3, dtype=int)
            for sample in SAMPLES:
                image = load_image(sample)
                detected = method(ink_mask(image))
                if filtered:
                    detected = typical_size_filter(detected)
                truth = load_truth(sample)
                s = score(detected, truth)
                totals += (s["found"], s["truth"], s["detected"])
                precision = s["found"] / s["detected"] if s["detected"] else 0.0
                print(
                    f"{name:11} {'size' if filtered else '-':6} {sample:8} "
                    f"{s['found']:>4}/{s['truth']:<4} {s['checked_found']:>3}/{s['checked']:<4} "
                    f"{s['empty_found']:>3}/{s['empty']:<4} {s['found']:>4}/{s['detected']:<5} {s['mean_iou']:.2f}"
                )
                if filtered and "--draw" in sys.argv:
                    draw(image, detected, truth, s["matched"], OUT / f"02_{name}_{sample}.png")
            print(
                f"{name:11} {'size' if filtered else '-':6} {'ALL':8} "
                f"{totals[0]:>4}/{totals[1]:<4} {'':17} {totals[0]:>4}/{totals[2]:<5}\n"
            )


if __name__ == "__main__":
    main()
