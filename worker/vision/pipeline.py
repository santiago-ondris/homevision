from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from vision.candidates import find_candidates
from vision.classify import classify
from vision.ink import ink_mask
from vision.params import Params
from vision.sizing import typical_size_filter
from vision.types import DetectionResult


def detect(image: NDArray[np.uint8], params: Params) -> DetectionResult:
    started = perf_counter()
    ink = ink_mask(image)
    ink_finished = perf_counter()
    candidates = find_candidates(ink, params)
    candidates_finished = perf_counter()
    boxes = typical_size_filter(candidates, params)
    sizing_finished = perf_counter()
    ordered = sorted(set(boxes), key=lambda box: (box.y1, box.x1))
    detections = tuple(classify(ink, box, params) for box in ordered)
    classify_finished = perf_counter()
    milliseconds_per_second = 1000
    timings = {
        "ink": (ink_finished - started) * milliseconds_per_second,
        "candidates": (candidates_finished - ink_finished) * milliseconds_per_second,
        "sizing": (sizing_finished - candidates_finished) * milliseconds_per_second,
        "classify": (classify_finished - sizing_finished) * milliseconds_per_second,
    }
    height, width = image.shape[:2]
    return DetectionResult(width, height, detections, timings)
