import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.logging import AsyncDatabaseHandler, setup_logging


# ── AsyncDatabaseHandler ─────────────────────────────────────────


class TestAsyncDatabaseHandlerEmit:
    def test_puts_record_on_queue(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)
        record = logging.LogRecord(
            name="test.logger", level=logging.INFO, pathname="",
            lineno=0, msg="hello", args=(), exc_info=None,
        )
        handler.emit(record)

        assert handler._queue.qsize() == 1

    def test_skips_sqlalchemy_records(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)
        record = logging.LogRecord(
            name="sqlalchemy.engine", level=logging.INFO, pathname="",
            lineno=0, msg="SELECT 1", args=(), exc_info=None,
        )
        handler.emit(record)

        assert handler._queue.qsize() == 0

    def test_handles_queue_full_gracefully(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)
        handler._queue = MagicMock()
        handler._queue.put_nowait = MagicMock(side_effect=Exception("queue full"))
        handler.handleError = MagicMock()

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="msg", args=(), exc_info=None,
        )
        handler.emit(record)

        handler.handleError.assert_called_once_with(record)


class TestAsyncDatabaseHandlerStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_consumer_task(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)

        with patch.object(handler, "_consumer", new_callable=AsyncMock):
            await handler.start()
            assert handler._task is not None
            # Clean up
            await handler._queue.put(None)
            await handler._task

    @pytest.mark.asyncio
    async def test_stop_sends_sentinel_and_awaits_task(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)

        # Create a real task that waits on the queue
        consumed = asyncio.Event()

        async def _fake_consumer():
            await handler._queue.get()  # waits for sentinel
            consumed.set()

        handler._task = asyncio.create_task(_fake_consumer())

        await handler.stop()
        assert consumed.is_set()


class TestAsyncDatabaseHandlerConsumer:
    @pytest.mark.asyncio
    async def test_consumer_writes_record_to_db(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)

        record = logging.LogRecord(
            name="test.logger", level=logging.WARNING, pathname="",
            lineno=0, msg="test message", args=(), exc_info=None,
        )
        record.method = "GET"
        record.path = "/api/v1/items"
        record.status_code = 200
        record.duration_ms = 12.5
        record.client_ip = "127.0.0.1"
        record.request_id = "abc123"

        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # add() is sync
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_sessionmaker = MagicMock(return_value=mock_session_ctx)

        # Put the record then the sentinel
        await handler._queue.put(record)
        await handler._queue.put(None)

        with patch("app.core.db.async_session", mock_sessionmaker):
            await handler._consumer()

        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

        # Verify the LogEntry was created with correct fields
        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.level == "WARNING"
        assert log_entry.logger_name == "test.logger"
        assert log_entry.message == "test message"
        assert log_entry.method == "GET"
        assert log_entry.path == "/api/v1/items"
        assert log_entry.status_code == 200
        assert log_entry.duration_ms == 12.5
        assert log_entry.client_ip == "127.0.0.1"
        assert log_entry.request_id == "abc123"
        assert log_entry.exception is None

    @pytest.mark.asyncio
    async def test_consumer_handles_record_with_exception_info(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)

        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger", level=logging.ERROR, pathname="",
            lineno=0, msg="something failed", args=(), exc_info=exc_info,
        )

        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # add() is sync
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_sessionmaker = MagicMock(return_value=mock_session_ctx)

        await handler._queue.put(record)
        await handler._queue.put(None)

        with patch("app.core.db.async_session", mock_sessionmaker):
            await handler._consumer()

        log_entry = mock_session.add.call_args[0][0]
        assert log_entry.exception is not None
        assert "ValueError: test error" in log_entry.exception

    @pytest.mark.asyncio
    async def test_consumer_swallows_db_errors(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)

        record = logging.LogRecord(
            name="test.logger", level=logging.INFO, pathname="",
            lineno=0, msg="msg", args=(), exc_info=None,
        )

        mock_session = AsyncMock()
        mock_session.add = MagicMock()  # add() is sync
        mock_session.commit = AsyncMock(side_effect=Exception("DB down"))
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_sessionmaker = MagicMock(return_value=mock_session_ctx)

        await handler._queue.put(record)
        await handler._queue.put(None)

        with patch("app.core.db.async_session", mock_sessionmaker):
            # Should not raise
            await handler._consumer()

    @pytest.mark.asyncio
    async def test_consumer_stops_on_sentinel(self):
        handler = AsyncDatabaseHandler(level=logging.DEBUG)
        await handler._queue.put(None)

        mock_sessionmaker = MagicMock()

        with patch("app.core.db.async_session", mock_sessionmaker):
            await handler._consumer()

        # The sessionmaker should never have been called since we only
        # sent the sentinel
        mock_sessionmaker.assert_not_called()


# ── setup_logging ────────────────────────────────────────────────


class TestSetupLogging:
    def test_creates_db_handler(self):
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.LOG_LEVEL = "INFO"
            mock_settings.LOG_FORMAT = "console"

            setup_logging()

        from app.core import logging as logging_mod
        assert logging_mod.db_handler is not None
        assert isinstance(logging_mod.db_handler, AsyncDatabaseHandler)

        # Clean up: remove the db_handler from root logger
        root = logging.getLogger()
        root.handlers = [
            h for h in root.handlers
            if not isinstance(h, AsyncDatabaseHandler)
        ]

    def test_db_handler_uses_configured_level(self):
        with patch("app.core.logging.settings") as mock_settings:
            mock_settings.LOG_LEVEL = "WARNING"
            mock_settings.LOG_FORMAT = "console"

            setup_logging()

        from app.core import logging as logging_mod
        assert logging_mod.db_handler is not None
        assert logging_mod.db_handler.level == logging.WARNING

        # Clean up
        root = logging.getLogger()
        root.handlers = [
            h for h in root.handlers
            if not isinstance(h, AsyncDatabaseHandler)
        ]
