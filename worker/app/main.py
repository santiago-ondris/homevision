import logging
import sys
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.config import Config, read_config
from app.errors import RequestError, error_response
from app.logging import configure_logging
from vision.params import Params
from vision.types import DetectionResult

MILLISECONDS_PER_SECOND = 1000


def detection_response(result: DetectionResult, decode_ms: float) -> JSONResponse:
    detection_ms = sum(result.timings_ms[name] for name in ("ink", "candidates", "sizing"))
    return JSONResponse(
        content={
            "image": {"width": result.width, "height": result.height},
            "boxes": [
                {
                    "bbox": [item.bbox.x1, item.bbox.y1, item.bbox.x2, item.bbox.y2],
                    "is_checked": item.is_checked,
                    "fill_ratio": round(item.fill_ratio, 3),
                }
                for item in result.boxes
            ],
            "timings_ms": {
                "decode": round(decode_ms, 1),
                "detect": round(detection_ms, 1),
                "classify": round(result.timings_ms["classify"], 1),
            },
        }
    )


async def log_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.url.path == "/healthz":
        return await call_next(request)
    started = perf_counter()
    request.state.metrics = {
        "request_id": request.headers.get("X-Request-Id", ""),
        **dict.fromkeys(("bytes", "width", "height", "boxes"), 0),
        "timings_ms": dict.fromkeys(("decode", "ink", "candidates", "sizing", "classify"), 0.0),
    }
    exception = None
    try:
        response = await call_next(request)
    except Exception:
        exception = sys.exc_info()
        response = error_response(
            RequestError(500, "internal_error", "The image could not be processed. Try again.")
        )
    metrics = request.state.metrics
    metrics["status"] = response.status_code
    metrics["duration_ms"] = (perf_counter() - started) * MILLISECONDS_PER_SECOND
    logging.getLogger(__name__).log(
        logging.ERROR if exception else logging.INFO,
        "detect request",
        extra=metrics,
        exc_info=exception,
    )
    return response


async def read_image_body(request: Request) -> bytes:
    if request.headers.get("Content-Type") not in ("image/png", "image/jpeg"):
        raise RequestError(415, "unsupported_media_type", "Send a PNG or JPEG image.")
    config = cast(Config, request.app.state.config)
    body = bytearray()
    async for chunk in request.stream():
        request.state.metrics["bytes"] += len(chunk)
        if request.state.metrics["bytes"] > config.max_upload_bytes:
            raise RequestError(
                413,
                "file_too_large",
                f"The image exceeds the {config.max_upload_bytes} byte limit.",
            )
        body.extend(chunk)
    return bytes(body)


def detect_image(
    request: Request, body: Annotated[bytes, Depends(read_image_body)]
) -> JSONResponse:
    # OpenCV must be imported after startup configures its allocation limit.
    from vision.decode import InvalidImageError, decode
    from vision.pipeline import detect

    config = cast(Config, request.app.state.config)
    params = cast(Params, request.app.state.params)
    started = perf_counter()
    try:
        image = decode(body, config.image_limits)
    except InvalidImageError as error:
        raise RequestError(422, "invalid_image", str(error)) from error
    decode_ms = (perf_counter() - started) * MILLISECONDS_PER_SECOND
    request.state.metrics.update(width=image.shape[1], height=image.shape[0])
    request.state.metrics["timings_ms"]["decode"] = decode_ms
    result = detect(image, params)
    request.state.metrics.update(
        boxes=len(result.boxes), timings_ms={"decode": decode_ms, **result.timings_ms}
    )
    return detection_response(result, decode_ms)


def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    configure_logging()
    try:
        config = read_config()
    except ValueError as error:
        logging.getLogger(__name__).error("Invalid configuration: %s", error)
        sys.exit(1)
    app = FastAPI()
    app.state.config = config
    app.state.params = Params()

    @app.exception_handler(RequestError)
    async def handle_request_error(request: Request, error: RequestError) -> JSONResponse:
        return error_response(error)

    app.middleware("http")(log_request)
    app.add_api_route("/v1/detect", detect_image, methods=["POST"])
    app.add_api_route("/healthz", health, methods=["GET"])
    return app


app = create_app()
