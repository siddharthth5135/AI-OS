import logging
import sys
from typing import Any

import structlog
from structlog.stdlib import BoundLogger, ProcessorFormatter


def mask_sensitive_data_processor(logger, log_method, event_dict):
    import re

    def mask_val(val):
        if isinstance(val, str):
            # Mask JWT tokens (starts with eyJ...)
            val = re.compile(
                r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"
            ).sub("[MASKED_TOKEN]", val)
            # Mask token query parameter in URLs
            val = re.compile(r"token=[A-Za-z0-9-_.]+").sub("token=[MASKED]", val)
            # Mask inline passwords in strings (e.g. JSON strings or db URIs)
            val = re.compile(
                r'password["\']?\s*:\s*["\']?[^"\',\s]+["\']?', re.IGNORECASE
            ).sub('password": "[MASKED]"', val)
            val = re.compile(r"postgres:[^@]+@").sub("postgres:[MASKED]@", val)
        return val

    # Mask fields in event_dict
    for k, v in list(event_dict.items()):
        if k in ["password", "api_key", "token", "secret"]:
            event_dict[k] = "[MASKED]"
        else:
            event_dict[k] = mask_val(v)

    # Also mask in the main event string
    if "event" in event_dict:
        event_dict["event"] = mask_val(event_dict["event"])

    return event_dict


def add_service_and_request_id_processor(logger, log_method, event_dict):
    event_dict["service"] = "ai-os"
    if "request_id" not in event_dict:
        import structlog

        ctx = structlog.contextvars.get_contextvars()
        event_dict["request_id"] = ctx.get("request_id", "unknown")
    return event_dict


def setup_logging(debug: bool = False) -> None:
    """
    Configures structlog for the application.
    - Production: JSON output
    - Development: Pretty console output
    Redirects standard library logging to structlog.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Shared processors
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        mask_sensitive_data_processor,
        add_service_and_request_id_processor,
    ]

    if debug:
        # Development: Console output with colors
        formatter_processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Production: JSON output with service metadata
        formatter_processor = structlog.processors.JSONRenderer()

    # Configure structlog
    structlog.configure(
        processors=processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ProcessorFormatter(
            processor=formatter_processor,
            foreign_pre_chain=processors,
        )
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Configure handlers for external libraries
    for name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "gunicorn",
        "gunicorn.access",
        "gunicorn.error",
    ):
        lib_logger = logging.getLogger(name)
        lib_logger.handlers = [handler]
        lib_logger.propagate = False
        lib_logger.setLevel(log_level)


def get_logger(name: str) -> BoundLogger:
    """
    Returns a bound structlog logger.
    """
    return structlog.get_logger(name)
