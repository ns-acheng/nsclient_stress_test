"""
Unit tests for Windows power management.

Tests Windows-specific power management functionality including:
- Sleep state transitions (S0, S1, S4)
- PwrTest.exe integration
- Wake timer configuration
- powercfg command parsing
- System reboot

All tests use mocking to avoid actual system operations.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from subprocess import CalledProcessError


@pytest.mark.windows
@pytest.mark.unit
class TestWindowsPowerManager:
    """Unit tests for WindowsPowerManager class."""

    @patch("platforms.windows.power.subprocess.run")
    def test_powercfg_output_success(self, mock_run):
        """Test successful powercfg /a command execution."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Standby (S0 Low Power Idle)\nStandby (S1)\nHibernate"
        )

        mgr = WindowsPowerManager()
        output = mgr._powercfg_output()

        assert "Standby (S0 Low Power Idle)" in output
        assert "Hibernate" in output
        mock_run.assert_called_once()
        # Verify correct command
        cmd_called = mock_run.call_args[0][0]
        assert "powercfg" in cmd_called[-1]
        assert "/a" in cmd_called[-1]

    @patch("platforms.windows.power.subprocess.run")
    def test_powercfg_output_failure(self, mock_run):
        """Test powercfg command failure handling."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        mgr = WindowsPowerManager()
        output = mgr._powercfg_output()

        assert output == ""

    @patch("platforms.windows.power.subprocess.run")
    def test_powercfg_output_exception(self, mock_run):
        """Test powercfg command exception handling."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.side_effect = Exception("Command failed")

        mgr = WindowsPowerManager()
        output = mgr._powercfg_output()

        assert output == ""

    @patch("platforms.windows.power.subprocess.run")
    def test_is_s0_low_power_idle_true(self, mock_run):
        """Test detection of S0 Low Power Idle support (AOAC)."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Standby (S0 Low Power Idle) Network Connected"
        )

        mgr = WindowsPowerManager()
        result = mgr._is_s0_low_power_idle()

        assert result == True

    @patch("platforms.windows.power.subprocess.run")
    def test_is_s0_low_power_idle_false(self, mock_run):
        """Test detection when S0 Low Power Idle not supported."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Standby (S1)\nHibernate"
        )

        mgr = WindowsPowerManager()
        result = mgr._is_s0_low_power_idle()

        assert result == False

    @patch("platforms.windows.power.os.path.exists")
    @patch("platforms.windows.power.subprocess.run")
    def test_run_pwrtest_success(self, mock_run, mock_exists):
        """Test successful PwrTest.exe execution."""
        from platforms.windows.power import WindowsPowerManager

        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        mgr = WindowsPowerManager()
        result = mgr._run_pwrtest(["/cs", "/c:1"])

        assert result == True
        mock_run.assert_called_once()
        # Verify pwrtest.exe in command
        cmd_called = mock_run.call_args[0][0]
        assert any("pwrtest.exe" in str(arg) for arg in cmd_called)

    @patch("platforms.windows.power.os.path.exists")
    def test_run_pwrtest_not_found(self, mock_exists):
        """Test PwrTest.exe not found."""
        from platforms.windows.power import WindowsPowerManager

        mock_exists.return_value = False

        mgr = WindowsPowerManager()
        result = mgr._run_pwrtest(["/cs", "/c:1"])

        assert result == False

    @patch("platforms.windows.power.os.path.exists")
    @patch("platforms.windows.power.subprocess.run")
    def test_run_pwrtest_failure(self, mock_run, mock_exists):
        """Test PwrTest.exe execution failure."""
        from platforms.windows.power import WindowsPowerManager

        mock_exists.return_value = True
        mock_run.side_effect = CalledProcessError(1, ["pwrtest.exe"])

        mgr = WindowsPowerManager()
        result = mgr._run_pwrtest(["/sleep", "/s:1"])

        assert result == False

    @patch("platforms.windows.power.kernel32")
    def test_set_wake_timer_success(self, mock_kernel32):
        """Test wake timer creation."""
        from platforms.windows.power import WindowsPowerManager

        # Mock successful timer creation
        mock_kernel32.CreateWaitableTimerW.return_value = 12345  # Mock handle
        mock_kernel32.SetWaitableTimer.return_value = True

        mgr = WindowsPowerManager()
        handle = mgr._set_wake_timer(60)

        assert handle == 12345
        mock_kernel32.CreateWaitableTimerW.assert_called_once()
        mock_kernel32.SetWaitableTimer.assert_called_once()

    @patch("platforms.windows.power.kernel32")
    def test_set_wake_timer_create_failed(self, mock_kernel32):
        """Test wake timer creation failure."""
        from platforms.windows.power import WindowsPowerManager

        mock_kernel32.CreateWaitableTimerW.return_value = None

        mgr = WindowsPowerManager()
        handle = mgr._set_wake_timer(60)

        assert handle is None

    @patch("platforms.windows.power.kernel32")
    def test_set_wake_timer_set_failed(self, mock_kernel32):
        """Test wake timer set failure."""
        from platforms.windows.power import WindowsPowerManager

        mock_kernel32.CreateWaitableTimerW.return_value = 12345
        mock_kernel32.SetWaitableTimer.return_value = False

        mgr = WindowsPowerManager()
        handle = mgr._set_wake_timer(60)

        assert handle is None
        mock_kernel32.CloseHandle.assert_called_once_with(12345)

    @patch("platforms.windows.power.WindowsPowerManager._run_pwrtest")
    def test_enter_s0_and_wake_pwrtest_success(self, mock_pwrtest):
        """Test S0 sleep using PwrTest (primary path)."""
        from platforms.windows.power import WindowsPowerManager

        mock_pwrtest.return_value = True

        mgr = WindowsPowerManager()
        result = mgr.enter_s0_and_wake(60)

        assert result == True
        mock_pwrtest.assert_called_once_with(["/cs", "/c:1", "/p:60", "/d:0"])

    @patch("platforms.windows.power.user32")
    @patch("platforms.windows.power.kernel32")
    @patch("platforms.windows.power.WindowsPowerManager._run_pwrtest")
    def test_enter_s0_and_wake_fallback(self, mock_pwrtest, mock_kernel32, mock_user32):
        """Test S0 sleep using fallback (monitor off) when PwrTest fails."""
        from platforms.windows.power import WindowsPowerManager

        # PwrTest fails, fallback to monitor off
        mock_pwrtest.return_value = False
        mock_kernel32.CreateWaitableTimerW.return_value = 12345
        mock_kernel32.SetWaitableTimer.return_value = True

        mgr = WindowsPowerManager()
        result = mgr.enter_s0_and_wake(30)

        assert result == True
        # Verify monitor messages sent
        assert mock_user32.SendMessageW.call_count >= 2
        mock_kernel32.WaitForSingleObject.assert_called_once()
        mock_kernel32.CloseHandle.assert_called_once_with(12345)

    @patch("platforms.windows.power.kernel32")
    @patch("platforms.windows.power.WindowsPowerManager._run_pwrtest")
    def test_enter_s0_and_wake_fallback_timer_failed(self, mock_pwrtest, mock_kernel32):
        """Test S0 sleep fallback fails if wake timer creation fails."""
        from platforms.windows.power import WindowsPowerManager

        mock_pwrtest.return_value = False
        mock_kernel32.CreateWaitableTimerW.return_value = None  # Timer creation fails

        mgr = WindowsPowerManager()
        result = mgr.enter_s0_and_wake(60)

        assert result == False

    @patch("platforms.windows.power.WindowsPowerManager._run_pwrtest")
    def test_enter_s1_and_wake_pwrtest_success(self, mock_pwrtest):
        """Test S1 (Standby) sleep using PwrTest."""
        from platforms.windows.power import WindowsPowerManager

        mock_pwrtest.return_value = True

        mgr = WindowsPowerManager()
        result = mgr.enter_s1_and_wake(120)

        assert result == True
        mock_pwrtest.assert_called_once_with(["/sleep", "/s:1", "/c:1", "/p:120", "/d:0"])

    @patch("platforms.windows.power.ctypes.windll.powrprof")
    @patch("platforms.windows.power.kernel32")
    @patch("platforms.windows.power.WindowsPowerManager._run_pwrtest")
    def test_enter_s1_and_wake_fallback(self, mock_pwrtest, mock_kernel32, mock_powrprof):
        """Test S1 sleep using legacy SetSuspendState fallback."""
        from platforms.windows.power import WindowsPowerManager

        mock_pwrtest.return_value = False
        mock_kernel32.CreateWaitableTimerW.return_value = 12345
        mock_kernel32.SetWaitableTimer.return_value = True

        mgr = WindowsPowerManager()
        result = mgr.enter_s1_and_wake(60)

        assert result == True
        # Verify SetSuspendState called with S1 parameters (0, 0, 0)
        mock_powrprof.SetSuspendState.assert_called_once_with(0, 0, 0)
        mock_kernel32.CloseHandle.assert_called_once_with(12345)

    @patch("platforms.windows.power.WindowsPowerManager._enter_s4_legacy")
    @patch("platforms.windows.power.WindowsPowerManager._is_s0_low_power_idle")
    def test_enter_s4_and_wake_aoac_platform(self, mock_is_aoac, mock_s4_legacy):
        """Test S4 (Hibernate) on AOAC platform uses legacy path."""
        from platforms.windows.power import WindowsPowerManager

        # AOAC platform detected
        mock_is_aoac.return_value = True
        mock_s4_legacy.return_value = True

        mgr = WindowsPowerManager()
        result = mgr.enter_s4_and_wake(300)

        assert result == True
        mock_s4_legacy.assert_called_once_with(300)

    @patch("platforms.windows.power.WindowsPowerManager._is_s0_low_power_idle")
    @patch("platforms.windows.power.WindowsPowerManager._run_pwrtest")
    def test_enter_s4_and_wake_pwrtest_success(self, mock_pwrtest, mock_is_aoac):
        """Test S4 (Hibernate) using PwrTest on non-AOAC platform."""
        from platforms.windows.power import WindowsPowerManager

        mock_is_aoac.return_value = False
        mock_pwrtest.return_value = True

        mgr = WindowsPowerManager()
        result = mgr.enter_s4_and_wake(300)

        assert result == True
        mock_pwrtest.assert_called_once_with(["/sleep", "/s:s4", "/dt:60", "/p:300"])

    @patch("platforms.windows.power.WindowsPowerManager._enter_s4_legacy")
    @patch("platforms.windows.power.WindowsPowerManager._is_s0_low_power_idle")
    @patch("platforms.windows.power.WindowsPowerManager._run_pwrtest")
    def test_enter_s4_and_wake_fallback(self, mock_pwrtest, mock_is_aoac, mock_s4_legacy):
        """Test S4 falls back to legacy when PwrTest fails."""
        from platforms.windows.power import WindowsPowerManager

        mock_is_aoac.return_value = False
        mock_pwrtest.return_value = False
        mock_s4_legacy.return_value = True

        mgr = WindowsPowerManager()
        result = mgr.enter_s4_and_wake(300)

        assert result == True
        mock_s4_legacy.assert_called_once_with(300)

    @patch("platforms.windows.power.ctypes.windll.powrprof")
    @patch("platforms.windows.power.kernel32")
    def test_enter_s4_legacy_success(self, mock_kernel32, mock_powrprof):
        """Test legacy S4 (Hibernate) implementation."""
        from platforms.windows.power import WindowsPowerManager

        mock_kernel32.CreateWaitableTimerW.return_value = 12345
        mock_kernel32.SetWaitableTimer.return_value = True

        mgr = WindowsPowerManager()
        result = mgr._enter_s4_legacy(300)

        assert result == True
        # Verify SetSuspendState called with S4 parameters (1, 0, 0)
        mock_powrprof.SetSuspendState.assert_called_once_with(1, 0, 0)
        mock_kernel32.CloseHandle.assert_called_once_with(12345)

    @patch("platforms.windows.power.subprocess.run")
    def test_is_sleep_state_available_hibernate_true(self, mock_run):
        """Test detection of Hibernate availability."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="The following sleep states are available:\n  Hibernate\n  Standby (S1)"
        )

        mgr = WindowsPowerManager()
        result = mgr.is_sleep_state_available("Hibernate")

        assert result == True

    @patch("platforms.windows.power.subprocess.run")
    def test_is_sleep_state_available_hibernate_false(self, mock_run):
        """Test detection when Hibernate not available."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "The following sleep states are available:\n"
                "  Standby (S1)\n"
                "The following sleep states are not available:\n"
                "  Hibernate\n"
            )
        )

        mgr = WindowsPowerManager()
        result = mgr.is_sleep_state_available("Hibernate")

        assert result == False

    @patch("platforms.windows.power.subprocess.run")
    def test_is_sleep_state_available_s1_true(self, mock_run):
        """Test detection of S1 (Standby) availability."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Standby (S1)\nHibernate"
        )

        mgr = WindowsPowerManager()
        result = mgr.is_sleep_state_available("Standby (S1)")

        assert result == True

    @patch("platforms.windows.power.subprocess.run")
    def test_is_sleep_state_available_chinese_locale(self, mock_run):
        """Test detection with Chinese locale output."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="休眠\n待命 (S1)"
        )

        mgr = WindowsPowerManager()
        # Test Chinese translation
        result = mgr.is_sleep_state_available("Hibernate")

        assert result == True

    @patch("platforms.windows.power.subprocess.run")
    def test_is_sleep_state_available_exception(self, mock_run):
        """Test exception handling in sleep state check."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.side_effect = Exception("Command failed")

        mgr = WindowsPowerManager()
        result = mgr.is_sleep_state_available("Hibernate")

        assert result == False

    @patch("platforms.windows.power.subprocess.run")
    def test_reboot_success(self, mock_run):
        """Test system reboot command."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(returncode=0)

        mgr = WindowsPowerManager()
        mgr.reboot()

        # Verify shutdown command called
        mock_run.assert_called_once()
        cmd_called = mock_run.call_args[0][0]
        assert "shutdown" in cmd_called
        assert "/r" in cmd_called
        assert "/t" in cmd_called
        assert "0" in cmd_called

    @patch("platforms.windows.power.subprocess.run")
    def test_reboot_exception(self, mock_run):
        """Test reboot handles exceptions gracefully."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.side_effect = Exception("Reboot failed")

        mgr = WindowsPowerManager()
        # Should not raise exception
        mgr.reboot()

    @patch("platforms.windows.power.subprocess.run")
    def test_enable_wake_timers_success(self, mock_run):
        """Test enabling wake timers in power settings."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(returncode=0)

        mgr = WindowsPowerManager()
        result = mgr.enable_wake_timers()

        assert result == True
        # Verify three powercfg commands called
        assert mock_run.call_count == 3
        # Verify all commands contain powercfg
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0]
            assert "powercfg" in cmd

    @patch("platforms.windows.power.subprocess.run")
    def test_enable_wake_timers_failure(self, mock_run):
        """Test enabling wake timers failure."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.side_effect = CalledProcessError(1, ["powercfg"])

        mgr = WindowsPowerManager()
        result = mgr.enable_wake_timers()

        assert result == False

    def test_implements_interface(self):
        """Verify WindowsPowerManager implements IPowerManager interface."""
        from platforms.windows.power import WindowsPowerManager
        from interfaces.i_power import IPowerManager

        mgr = WindowsPowerManager()
        assert isinstance(mgr, IPowerManager)

        # Verify all interface methods exist
        assert hasattr(mgr, "enter_s0_and_wake")
        assert hasattr(mgr, "enter_s1_and_wake")
        assert hasattr(mgr, "enter_s4_and_wake")
        assert hasattr(mgr, "is_sleep_state_available")
        assert hasattr(mgr, "reboot")
        assert hasattr(mgr, "enable_wake_timers")

    @patch("platforms.windows.power.subprocess.run")
    def test_enter_s0_returns_bool(self, mock_run):
        """Test enter_s0_and_wake returns boolean."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(returncode=0, stdout="")

        mgr = WindowsPowerManager()
        result = mgr.enter_s0_and_wake(60)

        assert isinstance(result, bool)

    @patch("platforms.windows.power.subprocess.run")
    def test_is_sleep_state_available_returns_bool(self, mock_run):
        """Test is_sleep_state_available returns boolean."""
        from platforms.windows.power import WindowsPowerManager

        mock_run.return_value = MagicMock(returncode=0, stdout="Hibernate")

        mgr = WindowsPowerManager()
        result = mgr.is_sleep_state_available("Hibernate")

        assert isinstance(result, bool)
