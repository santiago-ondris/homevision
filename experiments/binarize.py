"""Experiment 1: which ink/paper conversion keeps checkbox borders and drops colour?

For every ground-truth box it checks whether all four printed sides survive
the conversion, and how much stray ink lands inside boxes that are empty.
"""

import cv2
import numpy as np

from common import OUT, SAMPLES, load_image, load_truth

BLOCK = 51  # neighbourhood of the adaptive threshold, in pixels
OFFSET = 15  # how much darker than the neighbourhood a pixel must be
SIDE_COVERAGE = 0.7


def gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def brightest_channel(image):
    # A coloured pixel has at least one high channel; only black/grey ink is low in all three.
    return image.max(axis=2)


def otsu(plane):
    _, mask = cv2.threshold(plane, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return mask > 0


def adaptive(plane):
    mask = cv2.adaptiveThreshold(
        plane, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, BLOCK, OFFSET
    )
    return mask > 0


VARIANTS = {
    "gray + otsu": lambda im: otsu(gray(im)),
    "gray + adaptive": lambda im: adaptive(gray(im)),
    "max channel + otsu": lambda im: otsu(brightest_channel(im)),
    "max channel + adaptive": lambda im: adaptive(brightest_channel(im)),
}


def sides_kept(ink, bbox):
    x1, y1, x2, y2 = bbox
    t = 3
    strips = [
        ink[y1 : y1 + t, x1 + t : x2 - t].max(axis=0),
        ink[y2 - t : y2, x1 + t : x2 - t].max(axis=0),
        ink[y1 + t : y2 - t, x1 : x1 + t].max(axis=1),
        ink[y1 + t : y2 - t, x2 - t : x2].max(axis=1),
    ]
    return all(s.mean() >= SIDE_COVERAGE for s in strips)


def interior_ink(ink, bbox):
    x1, y1, x2, y2 = bbox
    mx, my = (x2 - x1) // 4, (y2 - y1) // 4
    return float(ink[y1 + my : y2 - my, x1 + mx : x2 - mx].mean())


def main():
    print(f"{'variant':24} {'sample':8} {'borders kept':>13} {'empty interior ink':>19} {'page ink':>9}")
    for name, convert in VARIANTS.items():
        kept_total = boxes_total = 0
        for sample in SAMPLES:
            image = load_image(sample)
            ink = convert(image)
            truth = load_truth(sample)
            kept = sum(sides_kept(ink, b["bbox"]) for b in truth)
            empty = [interior_ink(ink, b["bbox"]) for b in truth if not b["is_checked"]]
            kept_total += kept
            boxes_total += len(truth)
            print(
                f"{name:24} {sample:8} {kept:>6}/{len(truth):<6} "
                f"{max(empty):>19.3f} {ink.mean():>9.3f}"
            )
            safe = name.replace(" + ", "_").replace(" ", "-")
            cv2.imwrite(str(OUT / f"bin_{safe}_{sample}.png"), np.where(ink, 0, 255).astype(np.uint8))
        print(f"{name:24} {'ALL':8} {kept_total:>6}/{boxes_total}\n")


if __name__ == "__main__":
    main()
