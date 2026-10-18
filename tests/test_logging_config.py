"""
Tests for src/invoice_generator/logging_config.py logging configuration.

This module tests logging setup including file handlers, console handlers,
log levels, and third-party logger suppression.
"""

import pytest
import logging
import sys
from datetime import datetime
from unittest.mock import MagicMock

from invoice_generator.logging_config import setup_logging, get_logger


class TestSetupLogging:
    """Tests for setup_logging function."""

    @pytest.fixture(autouse=True)
    def clean_root_logger(self):
        """Give each test a bare root logger and tidy up afterwards.

        `setup_logging` attaches a `FileHandler` to the root logger.
        Dropping it without closing it leaks the open log file into the
        rest of the suite (surfacing as a `ResourceWarning` whenever the
        garbage collector gets round to it), so close the handlers each
        test added and put the original ones back.
        """
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level
        root_logger.handlers.clear()

        yield

        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers[:] = original_handlers
        root_logger.setLevel(original_level)

    @pytest.fixture(autouse=True)
    def log_dir(self, tmp_path, monkeypatch):
        """Write logs to a temporary directory, not the working one."""
        log_dir = tmp_path / "logs"
        monkeypatch.setattr("invoice_generator.logging_config.LOG_DIR", str(log_dir))
        return log_dir

    @staticmethod
    def started_at(monkeypatch, *times):
        """Make successive runs start at each of `times`."""
        mock_datetime = MagicMock()
        mock_datetime.now.side_effect = list(times)
        monkeypatch.setattr("invoice_generator.logging_config.datetime", mock_datetime)

    def test_creates_log_directory_and_file(self, log_dir):
        """Should create the log directory and a log file inside it."""
        result = setup_logging()

        assert result.is_file()
        assert result.parent == log_dir.resolve()

    def test_log_is_named_after_start_time(self, log_dir, monkeypatch):
        """The file name is when the run started, so logs sort in order."""
        self.started_at(monkeypatch, datetime(2026, 10, 18, 13, 24, 1))

        result = setup_logging()

        assert result == (log_dir / "2026-10-18_13-24-01.log").resolve()

    def test_returns_absolute_path_to_log_file(self):
        """Should return absolute path to log file."""
        assert setup_logging().is_absolute()

    def test_file_handler_uses_info_level_by_default(self):
        """File handler should use INFO level by default."""

        root_logger = logging.getLogger()

        setup_logging()

        # Find the file handler
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        assert file_handler.level == logging.INFO

    def test_console_handler_uses_warning_level(self):
        """Console handler should use WARNING level."""

        root_logger = logging.getLogger()

        setup_logging()

        # Find the console handler. pytest attaches log-capture handlers
        # of its own, which are also StreamHandlers, so match on the
        # stream `setup_logging` writes to.
        console_handler = None
        for handler in root_logger.handlers:
            if (isinstance(handler, logging.StreamHandler)
                    and not isinstance(handler, logging.FileHandler)
                    and handler.stream is sys.stdout):
                console_handler = handler
                break

        assert console_handler is not None
        assert console_handler.level == logging.WARNING

    def test_accepts_custom_logging_level(self):
        """Should accept custom logging level."""

        root_logger = logging.getLogger()

        setup_logging(level=logging.DEBUG)

        # Root logger should be at DEBUG level
        assert root_logger.level == logging.DEBUG

        # File handler should be at DEBUG level
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        assert file_handler.level == logging.DEBUG

    def test_suppresses_third_party_loggers(self):
        """Should suppress verbose third-party loggers."""

        setup_logging()

        # Check that third-party loggers are suppressed
        assert logging.getLogger("urllib3").level == logging.WARNING
        assert logging.getLogger("googleapiclient").level == logging.WARNING
        assert logging.getLogger("google.auth").level == logging.WARNING

    def test_each_run_gets_its_own_log(self, log_dir, monkeypatch):
        """Later runs should leave earlier logs alone."""
        self.started_at(monkeypatch, datetime(2026, 9, 1, 9, 0, 0),
                        datetime(2026, 10, 1, 9, 0, 0))

        first = setup_logging()
        second = setup_logging()

        assert first != second
        assert sorted(path.name for path in log_dir.iterdir()) == [
            "2026-09-01_09-00-00.log", "2026-10-01_09-00-00.log"
        ]

    def test_run_in_the_same_second_appends(self, log_dir, monkeypatch):
        """Two runs starting in the same second share a file, so the
        second must add to it rather than overwrite it."""
        log_dir.mkdir()
        (log_dir / "2026-10-18_13-24-01.log").write_text("Earlier run\n")
        self.started_at(monkeypatch, datetime(2026, 10, 18, 13, 24, 1))

        log_file = setup_logging()
        logging.getLogger("test").info("Later run")
        for handler in logging.getLogger().handlers:
            handler.flush()

        assert log_file.read_text().startswith("Earlier run\n")
        assert "Later run" in log_file.read_text()

    def test_log_formatters_include_timestamp_and_level(self):
        """Log formatters should include timestamp, name, level, and message."""

        root_logger = logging.getLogger()

        setup_logging()

        # Find handlers and check formatters
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        assert file_handler.formatter is not None

        # The format string should contain these components
        fmt_str = file_handler.formatter._fmt
        assert "asctime" in fmt_str
        assert "name" in fmt_str
        assert "levelname" in fmt_str
        assert "message" in fmt_str


    def test_console_shows_level_and_message_only(self):
        """Console lines should be short: the detail is in the log file."""

        setup_logging()

        (console_handler,) = [
            handler for handler in logging.getLogger().handlers
            if type(handler) is logging.StreamHandler and handler.stream is sys.stdout
        ]
        record = logging.LogRecord(
            "invoice_generator.calendar_api", logging.WARNING, __file__, 1,
            "Could not refresh Google token; signing in again", None, None,
        )
        assert console_handler.format(record) == (
            "WARNING: Could not refresh Google token; signing in again"
        )

class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_logger_instance(self):
        """Should return logging.Logger instance."""
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_specified_name(self):
        """Logger should have the specified name."""
        logger = get_logger("my.test.module")
        assert logger.name == "my.test.module"

    def test_multiple_calls_return_same_logger(self):
        """Multiple calls with same name should return same logger instance."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")
        assert logger1 is logger2
