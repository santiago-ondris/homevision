import json
import logging
import logging.config


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            event["request_id"] = str(record.request_id)
        for name in ("status", "duration_ms", "bytes", "width", "height", "boxes", "timings_ms"):
            if hasattr(record, name):
                event[name] = getattr(record, name)
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event)


def configure_logging() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JSONFormatter}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                }
            },
            "root": {"handlers": ["stdout"], "level": "INFO"},
            "loggers": {
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                "uvicorn.access": {"handlers": [], "propagate": False},
            },
        },
    )
