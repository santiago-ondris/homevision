"""Experiment 4: is the share of ink inside a box enough to tell checked from empty?

The feature is measured on the ground-truth boxes, so detection errors do not
leak in. `inset` is how much of each side is skipped to stay clear of the
printed border.
"""

import numpy as np

from common import SAMPLES, load_image, load_truth
from detect import ink_mask

INSETS = (0.10, 0.15, 0.20, 0.25, 0.30)


def fill_ratio(ink, bbox, inset):
    x1, y1, x2, y2 = bbox
    dx = max(2, round((x2 - x1) * inset))
    dy = max(2, round((y2 - y1) * inset))
    return float((ink[y1 + dy : y2 - dy, x1 + dx : x2 - dx] > 0).mean())


def features(inset):
    """{sample: [(fill, is_checked, ambiguous, index)]}"""
    out = {}
    for sample in SAMPLES:
        ink = ink_mask(load_image(sample))
        out[sample] = [
            (fill_ratio(ink, t["bbox"], inset), t["is_checked"], t["ambiguous"], i)
            for i, t in enumerate(load_truth(sample))
        ]
    return out


def best_threshold(rows):
    """Midpoint of the widest gap that separates the two classes with fewest errors."""
    values = sorted({r[0] for r in rows})
    candidates = [(a + b) / 2 for a, b in zip(values, values[1:])]
    def errors(t):
        return sum((r[0] > t) != r[1] for r in rows)
    fewest = min(errors(t) for t in candidates)
    good = [t for t in candidates if errors(t) == fewest]
    return (good[0] + good[-1]) / 2


def main():
    for inset in INSETS:
        data = features(inset)
        print(f"inset {inset:.2f}")
        for sample, rows in data.items():
            clear = [r for r in rows if not r[2]]
            empty = sorted(r[0] for r in clear if not r[1])
            checked = sorted(r[0] for r in clear if r[1])
            print(
                f"  {sample}: empty max {empty[-1]:.3f} (2nd {empty[-2]:.3f})   "
                f"checked min {checked[0]:.3f} (2nd {checked[1]:.3f})"
            )
        # leave one image out: pick the threshold on three, test on the fourth
        for held_out in SAMPLES:
            train = [r for s, rows in data.items() if s != held_out for r in rows if not r[2]]
            threshold = best_threshold(train)
            test = data[held_out]
            wrong = [(r[3], round(r[0], 3), r[1], r[2]) for r in test if (r[0] > threshold) != r[1]]
            print(f"  held out {held_out}: threshold {threshold:.3f}, wrong {len(wrong)}/{len(test)} {wrong}")
        print()


if __name__ == "__main__":
    main()
