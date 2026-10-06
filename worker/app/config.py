import os
from dataclasses import dataclass

from vision.types import ImageLimits

DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"
MINIMUM_PORT = 1
MAXIMUM_PORT = 65535
DEFAULT_MAX_UPLOAD_BYTES = 20971520
DEFAULT_MAX_IMAGE_SIDE = 10000
DEFAULT_MAX_IMAGE_PIXELS = 40000000


@dataclass(frozen=True)
class Config:
    port: int
    host: str
    max_upload_bytes: int
    image_limits: ImageLimits


def positive_integer(name: str, default: int) -> int:
    value = os.environ.get(name, str(default))
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def read_config() -> Config:
    port = positive_integer("PORT", DEFAULT_PORT)
    if port > MAXIMUM_PORT:
        raise ValueError(f"PORT must be between {MINIMUM_PORT} and {MAXIMUM_PORT}")
    host = os.environ.get("HOST", DEFAULT_HOST)
    if not host.strip():
        raise ValueError("HOST must not be empty")
    limits = ImageLimits(
        positive_integer("MAX_IMAGE_SIDE", DEFAULT_MAX_IMAGE_SIDE),
        positive_integer("MAX_IMAGE_PIXELS", DEFAULT_MAX_IMAGE_PIXELS),
    )
    config = Config(
        port, host, positive_integer("MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES), limits
    )
    os.environ["OPENCV_IO_MAX_IMAGE_PIXELS"] = str(limits.max_pixels)
    return config
