from vision.params import Params
from vision.types import Box

MINIMUM_GROUP_CANDIDATES = 3


def typical_size_filter(boxes: list[Box], params: Params) -> list[Box]:
    if len(boxes) < MINIMUM_GROUP_CANDIDATES:
        return boxes
    best_members: list[Box] = []
    for candidate in boxes:
        members = [
            box
            for box in boxes
            if abs(box.width - candidate.width) <= params.size_tolerance * candidate.width
            and abs(box.height - candidate.height) <= params.size_tolerance * candidate.height
        ]
        if len(members) > len(best_members):
            best_members = members
    return best_members
