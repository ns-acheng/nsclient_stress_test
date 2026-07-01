from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.windows
@pytest.mark.unit
class TestWindowsServiceManager:
    @patch("platforms.windows.service.time.sleep")
    @patch("platforms.windows.service.time.monotonic")
    def test_wait_for_target_status_returns_true(self, mock_monotonic, mock_sleep):
        from platforms.windows.service import WindowsServiceManager

        mgr = WindowsServiceManager()
        mgr.get_service_status = MagicMock(
            side_effect=["START_PENDING", "START_PENDING", "RUNNING"]
        )
        mock_monotonic.side_effect = [0.0, 0.0, 1.0, 1.0, 2.0, 2.0]

        result = mgr._wait_for_target_status("stagentsvc", "RUNNING", 10)

        assert result is True
        assert mgr.get_service_status.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("platforms.windows.service.time.sleep")
    @patch("platforms.windows.service.time.monotonic")
    def test_wait_for_target_status_times_out(self, mock_monotonic, mock_sleep):
        from platforms.windows.service import WindowsServiceManager

        mgr = WindowsServiceManager()
        mgr.get_service_status = MagicMock(
            side_effect=["START_PENDING", "START_PENDING", "START_PENDING"]
        )
        mock_monotonic.side_effect = [0.0, 0.0, 1.0, 1.0, 11.0, 11.0]

        result = mgr._wait_for_target_status("stagentsvc", "RUNNING", 10)

        assert result is False
        assert mgr.get_service_status.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("platforms.windows.service.WindowsServiceManager._wait_for_target_status")
    @patch("platforms.windows.service.subprocess.run")
    def test_start_service_waits_for_running(
        self,
        mock_run,
        mock_wait,
    ):
        from platforms.windows.service import WindowsServiceManager

        mock_run.return_value = MagicMock(stdout="SERVICE_NAME: stagentsvc", stderr="")
        mock_wait.return_value = True

        mgr = WindowsServiceManager()
        result = mgr.start_service("stagentsvc")

        assert result is True
        mock_run.assert_called_once()
        mock_wait.assert_called_once_with("stagentsvc", "RUNNING", 90)