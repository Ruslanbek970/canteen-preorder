"""Logging (SPEC 14.8): JSON lines in production, readable lines in dev. Every record made while
a request is handled carries its `request_id` (bound by app.middleware.RequestIdMiddleware).
Standard `logging` loggers go through the same formatter, so all modules share one format."""

import logging
import sys

import structlog

SHARED = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
]


def setup_logging(*, json: bool, level: int = logging.INFO) -> None:
    renderer = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if json
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.canteen = True  # type: ignore[attr-defined]
    root = logging.getLogger()
    # Replace only our own handler: test tools (pytest caplog) keep theirs.
    root.handlers = [h for h in root.handlers if not getattr(h, "canteen", False)] + [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    # The access log is written by RequestIdMiddleware, with the request id.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    structlog.configure(
        processors=[*SHARED, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
