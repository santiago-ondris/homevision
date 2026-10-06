from dataclasses import dataclass


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


@dataclass(frozen=True)
class ImageLimits:
    max_side: int
    max_pixels: int


@dataclass(frozen=True)
class Detection:
    bbox: Box
    is_checked: bool
    fill_ratio: float


@dataclass(frozen=True)
class DetectionResult:
    width: int
    height: int
    boxes: tuple[Detection, ...]
    timings_ms: dict[str, float]
