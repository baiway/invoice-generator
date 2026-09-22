"""
Tests for src/logging_config.py logging configuration.

This module tests logging setup including file handlers, console handlers,
log levels, and third-party logger suppression.
"""

import pytest
import logging
import sys
from pathlib import Path

from src.logging_config import setup_logging, get_logger


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

    def test_creates_log_file_at_specified_path(self, tmp_path, monkeypatch):
        """Should create log file at the specified path."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

        setup_logging()

        assert log_file.exists()

    def test_returns_absolute_path_to_log_file(self, tmp_path, monkeypatch):
        """Should return absolute path to log file."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

        result = setup_logging()

        assert Path(result).is_absolute()
        assert str(log_file.resolve()) == result

    def test_file_handler_uses_info_level_by_default(self, tmp_path, monkeypatch):
        """File handler should use INFO level by default."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

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

    def test_console_handler_uses_warning_level(self, tmp_path, monkeypatch):
        """Console handler should use WARNING level."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

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

    def test_accepts_custom_logging_level(self, tmp_path, monkeypatch):
        """Should accept custom logging level."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

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

    def test_suppresses_third_party_loggers(self, tmp_path, monkeypatch):
        """Should suppress verbose third-party loggers."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

        root_logger = logging.getLogger()

        setup_logging()

        # Check that third-party loggers are suppressed
        assert logging.getLogger("urllib3").level == logging.WARNING
        assert logging.getLogger("googleapiclient").level == logging.WARNING
        assert logging.getLogger("google.auth").level == logging.WARNING
        assert logging.getLogger("fontTools").level == logging.CRITICAL
        assert logging.getLogger("fontTools.subset").level == logging.CRITICAL
        assert logging.getLogger("fontTools.ttLib").level == logging.CRITICAL
        assert logging.getLogger("weasyprint").level == logging.CRITICAL

    def test_file_handler_mode_overwrites(self, tmp_path, monkeypatch):
        """File handler should use mode='w' to overwrite existing logs."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

        # Create existing log file with content
        log_file.write_text("Old log content\n")

        root_logger = logging.getLogger()

        setup_logging()

        # Write a log message
        test_logger = logging.getLogger("test")
        test_logger.info("New log message")

        # Close handlers to flush
        for handler in root_logger.handlers:
            handler.close()

        # Log file should not contain old content
        log_content = log_file.read_text()
        assert "Old log content" not in log_content
        assert "New log message" in log_content

    def test_log_formatters_include_timestamp_and_level(self, tmp_path, monkeypatch):
        """Log formatters should include timestamp, name, level, and message."""
        log_file = tmp_path / "test.log"
        monkeypatch.setattr("src.logging_config.LOG_FILE", str(log_file))

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
