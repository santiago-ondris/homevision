import os

DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"
MINIMUM_PORT = 1
MAXIMUM_PORT = 65535


def validate_environment() -> None:
    value = os.environ.get("PORT", str(DEFAULT_PORT))
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError("PORT must be an integer") from error
    if not MINIMUM_PORT <= port <= MAXIMUM_PORT:
        raise ValueError(f"PORT must be between {MINIMUM_PORT} and {MAXIMUM_PORT}")
    host = os.environ.get("HOST", DEFAULT_HOST)
    if not host.strip():
        raise ValueError("HOST must not be empty")
