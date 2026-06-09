import logging
import os
import sys

import pytest

from util_log import LogSetup


class TestLogSetupInit:
    def test_default_timestamp_format(self):
        ls = LogSetup()
        ts = ls.get_timestamp()
        assert len(ts) == 15
        assert ts[8] == "-"
        assert ts[:8].isdigit()
        assert ts[9:].isdigit()

    def test_default_log_folder(self):
        ls = LogSetup()
        folder = ls.get_log_folder()
        assert folder.startswith(os.path.join("log", ""))
        assert ls.get_timestamp() in folder

    def test_existing_log_dir(self, tmp_path):
        d = str(tmp_path / "my_logs")
        ls = LogSetup(existing_log_dir=d)
        assert ls.get_log_folder() == d

    def test_existing_log_dir_uses_basename_as_timestamp(self, tmp_path):
        d = str(tmp_path / "20260224-120000")
        ls = LogSetup(existing_log_dir=d)
        assert ls.get_timestamp() == "20260224-120000"


class TestSetupLogging:
    def test_returns_logger(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        logger = ls.setup_logging()
        assert isinstance(logger, logging.Logger)

    def test_creates_log_folder(self, tmp_path):
        folder = str(tmp_path / "new_folder")
        ls = LogSetup(existing_log_dir=folder)
        ls.setup_logging()
        assert os.path.isdir(folder)

    def test_creates_log_file(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        ls.setup_logging()
        log_file = tmp_path / "stress_test.log"
        assert log_file.exists()

    def test_file_handler_present(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        logger = ls.setup_logging()
        handler_types = [type(h) for h in logger.handlers]
        assert logging.FileHandler in handler_types

    def test_console_handler_present(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        logger = ls.setup_logging()
        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types

    def test_logger_level_info(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        logger = ls.setup_logging()
        assert logger.level == logging.INFO

    def test_log_message_written_to_file(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        logger = ls.setup_logging()
        logger.info("test message from pytest")
        for h in logger.handlers:
            h.flush()
        log_file = tmp_path / "stress_test.log"
        content = log_file.read_text(encoding="utf-8")
        assert "test message from pytest" in content

    def test_clears_previous_handlers(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        logger = ls.setup_logging()
        count1 = len(logger.handlers)
        ls2 = LogSetup(existing_log_dir=str(tmp_path))
        logger2 = ls2.setup_logging()
        count2 = len(logger2.handlers)
        assert count1 == count2

    def test_paramiko_logger_warning(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        ls.setup_logging()
        assert logging.getLogger("paramiko").level == logging.WARNING

    def test_urllib3_logger_warning(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        ls.setup_logging()
        assert logging.getLogger("urllib3").level == logging.WARNING

    def test_formatter_pattern(self, tmp_path):
        ls = LogSetup(existing_log_dir=str(tmp_path))
        logger = ls.setup_logging()
        for h in logger.handlers:
            fmt = h.formatter._fmt
            assert "%(asctime)s" in fmt
            assert "%(levelname)s" in fmt
            assert "%(message)s" in fmt
