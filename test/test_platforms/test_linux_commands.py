"""
Unit tests for Linux platform-specific implementations.

Tests Linux-specific command strings and behaviors:
- systemctl service management commands
- Service status detection
- Process management (pgrep, kill)
- System information queries
- Power management stubs

All tests use mocking to avoid actual system operations.
"""

import pytest
import signal
import os
from unittest.mock import patch, MagicMock, call


@pytest.mark.linux
@pytest.mark.unit
class TestLinuxServiceManager:
    """Unit tests for LinuxServiceManager class."""

    @patch("platforms.linux.service.subprocess.run")
    def test_get_service_status_running(self, mock_run):
        """Test service status detection when service is active."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")

        mgr = LinuxServiceManager()
        status = mgr.get_service_status("netskope-stagent")

        assert status == "RUNNING"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["systemctl", "is-active", "netskope-stagent"]

    @patch("platforms.linux.service.subprocess.run")
    def test_get_service_status_stopped(self, mock_run):
        """Test service status detection when service is inactive."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.return_value = MagicMock(returncode=3, stdout="inactive\n")

        mgr = LinuxServiceManager()
        status = mgr.get_service_status("netskope-stagent")

        assert status == "STOPPED"

    @patch("platforms.linux.service.subprocess.run")
    def test_get_service_status_not_found(self, mock_run):
        """Test service status detection when service doesn't exist."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.return_value = MagicMock(returncode=4, stdout="")

        mgr = LinuxServiceManager()
        status = mgr.get_service_status("nonexistent-service")

        assert status == "NOT_FOUND"

    @patch("platforms.linux.service.subprocess.run")
    def test_start_service_success(self, mock_run):
        """Test successful service start."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.return_value = MagicMock(returncode=0, stdout="")

        mgr = LinuxServiceManager()
        result = mgr.start_service("netskope-stagent")

        assert result == True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["systemctl", "start", "netskope-stagent"]

    @patch("platforms.linux.service.subprocess.run")
    def test_start_service_failure(self, mock_run):
        """Test service start failure."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.return_value = MagicMock(returncode=1, stdout="Failed to start")

        mgr = LinuxServiceManager()
        result = mgr.start_service("netskope-stagent")

        assert result == False

    @patch("platforms.linux.service.subprocess.run")
    def test_stop_service_success(self, mock_run):
        """Test successful service stop with status verification."""
        from platforms.linux.service import LinuxServiceManager

        # First call: stop command, then is-active checks
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # stop command
            MagicMock(returncode=3, stdout="inactive\n"),  # is-active check
        ]

        mgr = LinuxServiceManager()
        result = mgr.stop_service("netskope-stagent", timeout=30)

        assert result == True
        assert mock_run.call_count == 2

    @patch("platforms.linux.service.subprocess.run")
    def test_stop_service_no_wait(self, mock_run):
        """Test service stop without waiting for confirmation."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.return_value = MagicMock(returncode=0, stdout="")

        mgr = LinuxServiceManager()
        result = mgr.stop_service("netskope-stagent", timeout=0)

        assert result == True
        mock_run.assert_called_once()

    @patch("platforms.linux.service.time.sleep")
    @patch("platforms.linux.service.subprocess.run")
    def test_stop_service_timeout(self, mock_run, mock_sleep):
        """Test service stop timeout."""
        from platforms.linux.service import LinuxServiceManager

        # Stop command succeeds, but service never stops
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=""),  # stop command
            MagicMock(returncode=0, stdout="active\n"),  # still running
            MagicMock(returncode=0, stdout="active\n"),  # still running
        ]

        mgr = LinuxServiceManager()
        result = mgr.stop_service("netskope-stagent", timeout=2)

        assert result == False

    @patch("platforms.linux.service.os.kill")
    @patch("platforms.linux.service.subprocess.run")
    def test_handle_non_stop_with_pid(self, mock_run, mock_kill):
        """Test handling non-stopping service by killing PID."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.return_value = MagicMock(returncode=0, stdout="MainPID=1234\n",
                                          stderr="")

        mgr = LinuxServiceManager()
        with patch.dict(signal.__dict__, {'SIGKILL': 9}):
            mgr.handle_non_stop("netskope-stagent", True, "/tmp/log")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "show" in cmd
        assert "MainPID" in cmd[-1]
        mock_kill.assert_called_once_with(1234, 9)

    @patch("platforms.linux.service.subprocess.run")
    def test_handle_non_stop_fallback_pgrep(self, mock_run):
        """Test fallback to pgrep when MainPID not available."""
        from platforms.linux.service import LinuxServiceManager

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="MainPID=0\n", stderr=""),
            MagicMock(returncode=0, stdout="5678\n", stderr=""),
        ]

        mgr = LinuxServiceManager()
        with patch.dict(signal.__dict__, {'SIGKILL': 9}):
            with patch("platforms.linux.service.os.kill") as mock_kill:
                mgr.handle_non_stop("netskope-stagent", True, "/tmp/log")
                mock_kill.assert_called_once_with(5678, 9)


@pytest.mark.linux
@pytest.mark.unit
class TestLinuxSystemInfo:
    """Unit tests for LinuxSystemInfo class."""

    @patch("platforms.linux.system.subprocess.run")
    def test_log_process_usage_success(self, mock_run):
        """Test logging process CPU and memory usage."""
        from platforms.linux.system import LinuxSystemInfo

        # pgrep returns PID, ps returns usage
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="1234\n"),  # pgrep
            MagicMock(returncode=0, stdout="%CPU RSS\n 12.5 102400\n"),  # ps
        ]

        mgr = LinuxSystemInfo()
        with patch("platforms.linux.system.os.makedirs"):
            with patch("builtins.open", create=True) as mock_open:
                result = mgr.log_process_usage("stagent", "/tmp/log")

        assert result == True
        assert mock_run.call_count == 2

    @patch("platforms.linux.system.os.geteuid", create=True)
    def test_enable_privilege_as_root(self, mock_geteuid):
        """Test privilege check when running as root."""
        from platforms.linux.system import LinuxSystemInfo

        mock_geteuid.return_value = 0

        mgr = LinuxSystemInfo()
        result = mgr.enable_privilege("SeDebugPrivilege")

        assert result == 0

    @patch("platforms.linux.system.os.geteuid", create=True)
    def test_enable_privilege_not_root(self, mock_geteuid):
        """Test privilege check when not running as root."""
        from platforms.linux.system import LinuxSystemInfo

        mock_geteuid.return_value = 1000

        mgr = LinuxSystemInfo()
        result = mgr.enable_privilege("SeDebugPrivilege")

        assert result == 1

    @patch("platforms.linux.system.subprocess.run")
    def test_set_startup_task_success(self, mock_run):
        """Test creating systemd startup service."""
        from platforms.linux.system import LinuxSystemInfo

        mock_run.return_value = MagicMock(returncode=0)

        mgr = LinuxSystemInfo()
        with patch.dict(os.__dict__, {'geteuid': lambda: 0}):
            with patch("builtins.open", create=True) as mock_open:
                result = mgr.set_startup_task("test-task", "echo hello")

        assert result == True
        # Should call daemon-reload and enable
        assert mock_run.call_count == 2

    @patch("platforms.linux.system.subprocess.run")
    def test_remove_startup_task(self, mock_run):
        """Test removing systemd startup service."""
        from platforms.linux.system import LinuxSystemInfo

        mock_run.return_value = MagicMock(returncode=0)

        mgr = LinuxSystemInfo()
        with patch("platforms.linux.system.os.path.exists", return_value=True):
            with patch("platforms.linux.system.os.remove") as mock_remove:
                mgr.remove_startup_task("test-task")

        # Should call disable, stop, remove, daemon-reload
        assert mock_run.call_count >= 3
        mock_remove.assert_called_once()

    @patch("platforms.linux.system.subprocess.run")
    def test_run_shell_script_success(self, mock_run):
        """Test running shell script successfully."""
        from platforms.linux.system import LinuxSystemInfo

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Script output\n",
            stderr=""
        )

        mgr = LinuxSystemInfo()
        mgr.run_shell_script("/tmp/test.sh", ["arg1", "arg2"])

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["/bin/bash", "/tmp/test.sh", "arg1", "arg2"]


@pytest.mark.linux
@pytest.mark.unit
class TestLinuxPowerManager:
    """Unit tests for LinuxPowerManager stub implementation."""

    def test_power_operations_return_false(self):
        """Test that all power operations return False (stub)."""
        from platforms.linux.power import LinuxPowerManager

        mgr = LinuxPowerManager()

        assert mgr.enter_s0_and_wake(60) == False
        assert mgr.enter_s1_and_wake(60) == False
        assert mgr.enter_s4_and_wake(300) == False
        assert mgr.is_sleep_state_available("S1") == False
        assert mgr.enable_wake_timers() == False

    def test_reboot(self):
        """Test reboot command."""
        from platforms.linux.power import LinuxPowerManager

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            mgr = LinuxPowerManager()
            mgr.reboot()

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "reboot" in cmd


@pytest.mark.linux
@pytest.mark.unit
class TestLinuxDiagnostics:
    """Unit tests for LinuxDiagnostics class."""

    @patch("platforms.linux.diag.glob.glob")
    def test_check_crash_dumps_found(self, mock_glob):
        """Test crash dump detection when dumps exist."""
        from platforms.linux.diag import LinuxDiagnostics

        mock_glob.return_value = ["/var/crash/netskope-crash.dump"]

        diag = LinuxDiagnostics()
        found, count = diag.check_crash_dumps()

        assert found == True
        assert count == 0

    @patch("platforms.linux.diag.glob.glob")
    def test_check_crash_dumps_not_found(self, mock_glob):
        """Test crash dump detection when no dumps exist."""
        from platforms.linux.diag import LinuxDiagnostics

        mock_glob.return_value = []

        diag = LinuxDiagnostics()
        found, count = diag.check_crash_dumps()

        assert found == False

    @patch("platforms.linux.diag.subprocess.run")
    @patch("platforms.linux.diag.os.path.exists")
    def test_collect_log_bundle_success(self, mock_exists, mock_run):
        """Test collecting diagnostic log bundle."""
        from platforms.linux.diag import LinuxDiagnostics

        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        diag = LinuxDiagnostics()
        with patch("platforms.linux.diag.os.makedirs"):
            diag.collect_log_bundle("20260325", True, "/tmp/output")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert any("nsdiag" in str(arg) for arg in cmd)
        assert "-o" in cmd

    @patch("platforms.linux.diag.subprocess.run")
    def test_generate_live_dump_gcore(self, mock_run):
        """Test generating live dump using gcore."""
        from platforms.linux.diag import LinuxDiagnostics

        mock_run.return_value = MagicMock(returncode=0)

        diag = LinuxDiagnostics()
        with patch("platforms.linux.diag.os.makedirs"):
            diag.generate_live_dump(1234, "/tmp/dumps")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "gcore" in cmd
        assert "1234" in cmd


@pytest.mark.linux
@pytest.mark.unit
class TestLinuxEnvironment:
    """Unit tests for LinuxEnvironment class."""

    def test_agent_paths(self):
        """Test Linux-specific paths."""
        from platforms.linux.env import LinuxEnvironment

        env = LinuxEnvironment()

        assert env.agent_data_dir == "/opt/netskope/stagent/data"
        assert env.agent_log_file == "/var/log/netskope/stagent/nsdebuglog.log"
        assert env.system_hosts_file == "/etc/hosts"


@pytest.mark.linux
@pytest.mark.unit
class TestLinuxFactory:
    """Unit tests for LinuxFactory class."""

    def test_factory_creates_all_managers(self):
        """Test that factory creates all required platform managers."""
        from platforms.linux.factory import LinuxFactory

        factory = LinuxFactory()

        power_mgr = factory.create_power_manager()
        service_mgr = factory.create_service_manager()
        system_info = factory.create_system_info()
        input_mon = factory.create_input_monitor()
        diag = factory.create_diagnostics()
        env = factory.create_environment()

        assert power_mgr is not None
        assert service_mgr is not None
        assert system_info is not None
        assert input_mon is not None
        assert diag is not None
        assert env is not None

    def test_factory_implements_interface(self):
        """Test that factory implements IPlatformFactory."""
        from platforms.linux.factory import LinuxFactory
        from interfaces.i_factory import IPlatformFactory

        factory = LinuxFactory()
        assert isinstance(factory, IPlatformFactory)

    def test_managers_implement_interfaces(self):
        """Test that created managers implement correct interfaces."""
        from platforms.linux.factory import LinuxFactory
        from interfaces.i_power import IPowerManager
        from interfaces.i_service import IServiceManager
        from interfaces.i_system import ISystemInfo
        from interfaces.i_input import IInputMonitor
        from interfaces.i_diag import IDiagnostics
        from interfaces.i_env import IEnvironment

        factory = LinuxFactory()

        assert isinstance(factory.create_power_manager(), IPowerManager)
        assert isinstance(factory.create_service_manager(), IServiceManager)
        assert isinstance(factory.create_system_info(), ISystemInfo)
        assert isinstance(factory.create_input_monitor(), IInputMonitor)
        assert isinstance(factory.create_diagnostics(), IDiagnostics)
        assert isinstance(factory.create_environment(), IEnvironment)
