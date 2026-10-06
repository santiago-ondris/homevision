import logging
import sys

from fastapi import FastAPI, Request

from app.config import validate_environment
from app.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    try:
        validate_environment()
    except ValueError as error:
        logging.getLogger(__name__).error("Invalid configuration: %s", error)
        sys.exit(1)
    app = FastAPI()

    @app.get("/healthz")
    def health(request: Request) -> dict[str, str]:
        logging.getLogger(__name__).info(
            "health check", extra={"request_id": request.headers.get("X-Request-Id", "")}
        )
        return {"status": "ok"}

    return app


app = create_app()
