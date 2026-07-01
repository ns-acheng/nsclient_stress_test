import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.windows
@pytest.mark.unit
class TestWindowsDiagnostics:
    @patch("platforms.windows.diag.subprocess.run")
    def test_export_event_log_success(self, mock_run):
        from platforms.windows.diag import WindowsDiagnostics

        mock_run.return_value = MagicMock(returncode=0)

        diag = WindowsDiagnostics()
        ok = diag._export_event_log("System", "20260413_120000", "C:/logs")

        assert ok is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["wevtutil", "epl", "System"]
        assert cmd[-1] == "/ow:true"
        assert cmd[3].endswith("20260413_120000_event_System.evtx")

    @patch("platforms.windows.diag.subprocess.run")
    def test_collect_windows_event_logs_exports_both_logs(self, mock_run):
        from platforms.windows.diag import WindowsDiagnostics

        mock_run.return_value = MagicMock(returncode=0)

        diag = WindowsDiagnostics()
        diag._collect_windows_event_logs("20260413_120000", "C:/logs")

        assert mock_run.call_count == 2
        first = mock_run.call_args_list[0][0][0]
        second = mock_run.call_args_list[1][0][0]
        assert first[2] == "System"
        assert second[2] == "Application"

    @patch("platforms.windows.diag.WindowsDiagnostics._collect_windows_event_logs")
    @patch("platforms.windows.diag.WindowsDiagnostics._run_nsdiag")
    @patch("platforms.windows.diag.os.makedirs")
    @patch("platforms.windows.diag.os.path.exists")
    def test_collect_log_bundle_also_collects_event_logs(
        self,
        mock_exists,
        mock_makedirs,
        mock_run_nsdiag,
        mock_collect_event_logs,
    ):
        from platforms.windows.diag import WindowsDiagnostics

        mock_exists.return_value = False
        mock_run_nsdiag.return_value = True

        diag = WindowsDiagnostics()
        diag.collect_log_bundle("20260413_120000", True, "C:/logs")

        mock_makedirs.assert_called_once_with("C:/logs")
        mock_run_nsdiag.assert_called_once_with(
            diag.nsdiag_path,
            ["-o", os.path.join("C:/logs", "20260413_120000_log_bundle.zip")],
            "log collection",
        )
        mock_collect_event_logs.assert_called_once_with("20260413_120000", "C:/logs")

    @patch("platforms.windows.diag.os.path.exists")
    @patch("platforms.windows.diag.subprocess.run")
    def test_run_nsdiag_uses_timeout(self, mock_run, mock_exists):
        from platforms.windows.diag import NSDIAG_TIMEOUT_SEC, WindowsDiagnostics

        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        diag = WindowsDiagnostics()
        ok = diag._run_nsdiag(diag.nsdiag_path, ["-u"], "config update")

        assert ok is True
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["timeout"] == NSDIAG_TIMEOUT_SEC

    @patch("platforms.windows.diag.os.path.exists")
    @patch("platforms.windows.diag.subprocess.run")
    def test_run_nsdiag_timeout_returns_false(self, mock_run, mock_exists):
        from platforms.windows.diag import WindowsDiagnostics
        from subprocess import TimeoutExpired

        mock_exists.return_value = True
        mock_run.side_effect = TimeoutExpired(["nsdiag.exe", "-u"], 300)

        diag = WindowsDiagnostics()
        ok = diag._run_nsdiag(diag.nsdiag_path, ["-u"], "config update")

        assert ok is False
