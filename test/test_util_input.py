import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

import util_input


class TestStartInputMonitor:
    def test_dispatches_to_windows_on_win32(self, stop_event):
        with patch.object(util_input, "sys") as mock_sys:
            mock_sys.platform = "win32"
            with patch.object(
                util_input, "_start_windows_monitor"
            ) as mock_win:
                util_input.start_input_monitor(stop_event)
                mock_win.assert_called_once_with(stop_event)

    def test_dispatches_to_unix_on_linux(self, stop_event):
        with patch.object(util_input, "sys") as mock_sys:
            mock_sys.platform = "linux"
            with patch.object(
                util_input, "_start_unix_monitor"
            ) as mock_unix:
                util_input.start_input_monitor(stop_event)
                mock_unix.assert_called_once_with(stop_event)

    def test_dispatches_to_unix_on_darwin(self, stop_event):
        with patch.object(util_input, "sys") as mock_sys:
            mock_sys.platform = "darwin"
            with patch.object(
                util_input, "_start_unix_monitor"
            ) as mock_unix:
                util_input.start_input_monitor(stop_event)
                mock_unix.assert_called_once_with(stop_event)


class TestWindowsMonitor:
    def test_esc_sets_stop_event(self, stop_event):
        mock_msvcrt = MagicMock()
        mock_msvcrt.kbhit.side_effect = [False, True]
        mock_msvcrt.getch.return_value = b'\x1b'

        with patch.dict(sys.modules, {"msvcrt": mock_msvcrt}):
            with patch.object(util_input, "time") as mock_time:
                mock_time.sleep = MagicMock()
                util_input._start_windows_monitor(stop_event)
                import time
                time.sleep(0.3)

        assert stop_event.is_set()

    def test_non_esc_key_does_not_stop(self, stop_event):
        mock_msvcrt = MagicMock()
        call_count = 0

        def _kbhit():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True
            if call_count >= 3:
                stop_event.set()
            return False

        mock_msvcrt.kbhit.side_effect = _kbhit
        mock_msvcrt.getch.return_value = b'a'

        with patch.dict(sys.modules, {"msvcrt": mock_msvcrt}):
            with patch.object(util_input, "time") as mock_time:
                mock_time.sleep = MagicMock()
                util_input._start_windows_monitor(stop_event)
                import time
                time.sleep(0.3)

        assert stop_event.is_set()
