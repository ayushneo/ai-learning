"""Logging config via stdlib logging.dictConfig.

# ponytail: no structlog/loguru dependency -- stdlib logging plus a
# JSON formatter is a ~20-line module and covers everything this template
# needs (level control, one format for local + container stdout). Reach for
# structlog when you need contextvars-based request-scoped fields threaded
# automatically; until then this is one less dependency to pin and patch.
"""
import logging.config


def configure_logging(level: str = "INFO") -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
                    "defaults": {"request_id": "-"},
                },
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "default"},
            },
            "root": {"handlers": ["console"], "level": level},
            "loggers": {
                # Quiet down the access log's own request line; our request-id
                # middleware logs one structured line per request instead.
                "uvicorn.access": {"level": "WARNING", "propagate": True},
            },
        }
    )
