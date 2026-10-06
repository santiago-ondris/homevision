from vision.types import Box


def intersection_over_union(first: Box, second: Box) -> float:
    width = max(0, min(first.x2, second.x2) - max(first.x1, second.x1))
    height = max(0, min(first.y2, second.y2) - max(first.y1, second.y1))
    intersection = width * height
    union = first.width * first.height + second.width * second.height - intersection
    return intersection / union if union else 0.0


def match_boxes(detected: list[Box], truth: list[Box]) -> dict[int, int]:
    minimum_overlap = 0.5
    pairs = sorted(
        (
            (intersection_over_union(box, expected), detected_index, truth_index)
            for detected_index, box in enumerate(detected)
            for truth_index, expected in enumerate(truth)
        ),
        reverse=True,
    )
    matched: dict[int, int] = {}
    used: set[int] = set()
    for overlap, detected_index, truth_index in pairs:
        if overlap < minimum_overlap:
            break
        if truth_index not in matched and detected_index not in used:
            matched[truth_index] = detected_index
            used.add(detected_index)
    return matched
