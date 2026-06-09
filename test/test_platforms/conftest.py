"""Platform-specific test fixtures and configuration."""

import sys
import pytest
from unittest.mock import MagicMock, patch


def pytest_configure(config):
    """Register custom markers for platform-specific tests."""
    config.addinivalue_line("markers", "windows: Windows-specific tests")
    config.addinivalue_line("markers", "linux: Linux-specific tests")
    config.addinivalue_line("markers", "macos: macOS-specific tests")
    config.addinivalue_line("markers", "android: Android device tests")
    config.addinivalue_line("markers", "ios: iOS device tests")
    config.addinivalue_line("markers", "unit: Pure unit tests (fully mocked)")
    config.addinivalue_line("markers", "integration: Integration tests (real services)")


@pytest.fixture
def current_platform():
    """Returns current platform name."""
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform.startswith("darwin"):
        return "macos"
    return "unknown"


@pytest.fixture
def is_windows(current_platform):
    """Check if running on Windows."""
    return current_platform == "windows"


@pytest.fixture
def is_linux(current_platform):
    """Check if running on Linux."""
    return current_platform == "linux"


@pytest.fixture
def is_macos(current_platform):
    """Check if running on macOS."""
    return current_platform == "macos"


# Platform-specific command mocks

@pytest.fixture
def mock_systemctl_active():
    """Mock systemctl is-active command for Linux tests."""
    mock = MagicMock()
    mock.stdout = "active\n"
    mock.returncode = 0
    return mock


@pytest.fixture
def mock_systemctl_inactive():
    """Mock systemctl is-active command returning inactive."""
    mock = MagicMock()
    mock.stdout = "inactive\n"
    mock.returncode = 3
    return mock


@pytest.fixture
def mock_systemctl_show_pid():
    """Mock systemctl show command with PID."""
    mock = MagicMock()
    mock.stdout = "MainPID=1234\n"
    mock.returncode = 0
    return mock


# Interface mock fixtures (platform-aware)

@pytest.fixture
def mock_power_mgr_platform_aware(current_platform):
    """
    Returns appropriate power manager mock based on platform.

    Windows: Full power management support
    Linux/Android/iOS: Stub implementation (returns False)
    """
    from interfaces.i_power import IPowerManager

    mgr = MagicMock(spec=IPowerManager)

    if current_platform == "windows":
        # Full power management support
        mgr.enter_s0_and_wake.return_value = True
        mgr.enter_s1_and_wake.return_value = True
        mgr.enter_s4_and_wake.return_value = True
        mgr.is_sleep_state_available.return_value = True
        mgr.enable_wake_timers.return_value = True
    else:
        # No power management on other platforms (stub)
        mgr.enter_s0_and_wake.return_value = False
        mgr.enter_s1_and_wake.return_value = False
        mgr.enter_s4_and_wake.return_value = False
        mgr.is_sleep_state_available.return_value = False
        mgr.enable_wake_timers.return_value = False

    return mgr


@pytest.fixture
def mock_service_mgr():
    """Generic service manager mock for testing."""
    from interfaces.i_service import IServiceManager

    mgr = MagicMock(spec=IServiceManager)
    mgr.start_service.return_value = True
    mgr.stop_service.return_value = True
    mgr.get_service_status.return_value = "RUNNING"
    mgr.handle_non_stop.return_value = None
    return mgr


@pytest.fixture
def mock_system_info():
    """Generic system info mock for testing."""
    from interfaces.i_system import ISystemInfo

    info = MagicMock(spec=ISystemInfo)
    info.get_memory_usage.return_value = (60, 8192)
    info.enable_privilege.return_value = 0
    info.get_process_pid.return_value = 1234
    info.set_startup_task.return_value = True
    return info
