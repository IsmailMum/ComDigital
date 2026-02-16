"""
Centralised logging configuration for the application.

Call ``setup_logging()`` once at startup (before any request is served) to
configure the root logger with a consistent format and level.
"""

import asyncio
import logging
import sys
import traceback
from datetime import datetime, timezone

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    This is ideal for production environments where logs are ingested by
    aggregation tools (ELK, CloudWatch, Datadog, etc.).
    """

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Attach extra fields added by middleware / application code
        for attr in ("method", "path", "status_code", "duration_ms", "client_ip", "request_id"):
            value = getattr(record, attr, None)
            if value is not None:
                log_entry[attr] = value

        return json.dumps(log_entry, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable coloured formatter for local development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        base = f"{color}{timestamp} | {record.levelname:<8}{self.RESET} | {record.name} - {record.getMessage()}"

        # Append extra context when present (e.g. from request middleware)
        extras = []
        for attr in ("method", "path", "status_code", "duration_ms", "client_ip"):
            value = getattr(record, attr, None)
            if value is not None:
                extras.append(f"{attr}={value}")
        if extras:
            base += f" [{', '.join(extras)}]"

        if record.exc_info and record.exc_info[0] is not None:
            base += "\n" + self.formatException(record.exc_info)

        return base


class AsyncDatabaseHandler(logging.Handler):
    """Logging handler that queues records for async insertion into the DB.

    Call ``await start()`` once the event loop is running (e.g. in the
    FastAPI lifespan) and ``await stop()`` on shutdown.
    """

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._queue: asyncio.Queue[logging.LogRecord | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    # -- public API called from the lifespan -----------------------------------

    async def start(self) -> None:
        """Start the background consumer task."""
        self._task = asyncio.create_task(self._consumer())

    async def stop(self) -> None:
        """Signal the consumer to stop and wait for it to drain."""
        await self._queue.put(None)  # sentinel
        if self._task:
            await self._task

    # -- logging.Handler interface ---------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        # Skip SQLAlchemy-engine logs to avoid infinite recursion
        if record.name.startswith("sqlalchemy."):
            return
        try:
            self._queue.put_nowait(record)
        except Exception:
            self.handleError(record)

    # -- background consumer ---------------------------------------------------

    async def _consumer(self) -> None:
        # Deferred imports to avoid circular deps at module-load time
        from app.core.db import async_session
        from app.models import LogEntry

        while True:
            record = await self._queue.get()
            if record is None:  # shutdown sentinel
                break
            try:
                exc_text: str | None = None
                if record.exc_info and record.exc_info[0] is not None:
                    exc_text = "".join(traceback.format_exception(*record.exc_info))

                entry = LogEntry(
                    timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
                    level=record.levelname,
                    logger_name=record.name,
                    message=record.getMessage(),
                    method=getattr(record, "method", None),
                    path=getattr(record, "path", None),
                    status_code=getattr(record, "status_code", None),
                    duration_ms=getattr(record, "duration_ms", None),
                    client_ip=getattr(record, "client_ip", None),
                    request_id=getattr(record, "request_id", None),
                    exception=exc_text,
                )
                async with async_session() as session:
                    session.add(entry)
                    await session.commit()
            except Exception:
                # Never propagate DB errors back into logging
                pass


# Module-level reference so the lifespan can start/stop it
db_handler: AsyncDatabaseHandler | None = None


def setup_logging() -> None:
    """Configure the root logger for the entire application.

    * In **production** (``LOG_FORMAT=json``), logs are emitted as JSON.
    * In **development** (``LOG_FORMAT=console``), logs are human-readable
      with colour.

    The log level is controlled via the ``LOG_LEVEL`` setting
    (default ``INFO``).
    """
    global db_handler

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    log_format = settings.LOG_FORMAT.lower()

    # Choose formatter
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = ConsoleFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any pre-existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Database handler (started later by the lifespan)
    db_handler = AsyncDatabaseHandler(level=log_level)
    root_logger.addHandler(db_handler)

    # Quiet down noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if log_level <= logging.DEBUG else logging.WARNING
    )

    logging.getLogger(__name__).info(
        "Logging configured — level=%s, format=%s", settings.LOG_LEVEL, log_format,
    )
