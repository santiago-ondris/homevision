from vision.params import Params
from vision.types import Box

MINIMUM_GROUP_CANDIDATES = 3


def typical_size_filter(boxes: list[Box], params: Params) -> list[Box]:
    if len(boxes) < MINIMUM_GROUP_CANDIDATES:
        return boxes
    best_members: list[Box] = []
    best_score = 0
    for candidate in boxes:
        members = [
            box
            for box in boxes
            if abs(box.width - candidate.width) <= params.size_tolerance * candidate.width
            and abs(box.height - candidate.height) <= params.size_tolerance * candidate.height
        ]
        score = sum(box.width * box.height for box in members)
        if score > best_score:
            best_members = members
            best_score = score
    return best_members
