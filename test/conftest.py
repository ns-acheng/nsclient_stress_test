import json
import threading
from unittest.mock import MagicMock

import pytest

from interfaces.i_env import IEnvironment
from interfaces.i_service import IServiceManager
from interfaces.i_power import IPowerManager
from interfaces.i_system import ISystemInfo
from interfaces.i_input import IInputMonitor
from interfaces.i_diag import IDiagnostics


@pytest.fixture
def stop_event():
    return threading.Event()


@pytest.fixture
def mock_env(tmp_path):
    env = MagicMock(spec=IEnvironment)
    env.agent_data_dir = str(tmp_path / "agent_data")
    env.agent_log_file = str(tmp_path / "agent.log")
    env.system_hosts_file = str(tmp_path / "hosts")
    return env


@pytest.fixture
def mock_svc_mgr():
    mgr = MagicMock(spec=IServiceManager)
    mgr.start_service.return_value = True
    mgr.stop_service.return_value = True
    mgr.get_service_status.return_value = "running"
    return mgr


@pytest.fixture
def mock_power_mgr():
    mgr = MagicMock(spec=IPowerManager)
    mgr.enter_s0_and_wake.return_value = True
    mgr.enter_s1_and_wake.return_value = True
    mgr.enter_s4_and_wake.return_value = True
    mgr.is_sleep_state_available.return_value = True
    mgr.enable_wake_timers.return_value = True
    return mgr


@pytest.fixture
def mock_sys_info():
    info = MagicMock(spec=ISystemInfo)
    info.get_memory_usage.return_value = (60, 8192)
    info.enable_privilege.return_value = 0
    info.get_process_pid.return_value = 1234
    info.set_startup_task.return_value = True
    info.remove_startup_task = MagicMock()
    return info


@pytest.fixture
def mock_input_mon():
    return MagicMock(spec=IInputMonitor)


@pytest.fixture
def mock_diag():
    diag = MagicMock(spec=IDiagnostics)
    diag.check_crash_dumps.return_value = (False, 0)
    return diag


@pytest.fixture
def sample_urls():
    return [
        "https://www.google.com",
        "https://www.github.com",
        "https://www.example.com",
        "https://www.python.org",
        "https://www.microsoft.com",
    ]


@pytest.fixture
def minimal_config():
    return {
        "loop_times": 10,
        "stop_svc_interval": 1,
        "stop_drv_interval": 0,
        "reboot_interval": 0,
        "traffic_gen": {
            "https": {
                "enable": 1,
                "duration_sec": 0,
                "count": 60,
                "concurrent_conn": 30,
            }
        },
    }


@pytest.fixture
def full_config():
    return {
        "loop_times": 50,
        "stop_svc_interval": 2,
        "stop_drv_interval": 0,
        "reboot_interval": 0,
        "custom_dump_path": "",
        "long_idle_interval": 100,
        "long_idle_time_min": 300,
        "long_idle_time_max": 600,
        "client_feature_toggling": {
            "failclose": {"enable": 1, "interval": 15},
            "client_disabling": {
                "enable": 0,
                "enable_sec_min": 200,
                "enable_sec_max": 800,
                "disable_ratio": 0.2,
            },
        },
        "power_test": {
            "aoac_s0_standby": {
                "enable": 0,
                "interval": 2,
                "duration_sec": 60,
            },
            "aoac_s1_standby": {
                "enable": 0,
                "interval": 2,
                "duration_sec": 60,
            },
            "aoac_s4_hibernate": {
                "enable": 0,
                "interval": 2,
                "duration_sec": 60,
            },
        },
        "traffic_gen": {
            "browser": {
                "enable": 1,
                "max_memory": 70,
                "max_tabs": 15,
                "log_validation": 0,
            },
            "dns": {
                "enable": 1,
                "duration_sec": 10,
                "count": 100,
                "concurrent_conn": 20,
            },
            "udp": {
                "enable": 0,
                "duration_sec": 20,
                "count": 0,
                "concurrent_conn": 10,
                "target_ip": "192.168.1.1",
                "target_ipv6": "",
                "target_port": 8080,
            },
            "https": {
                "enable": 1,
                "duration_sec": 0,
                "count": 60,
                "concurrent_conn": 30,
                "log_validation": 0,
                "log_validation_ratio": 3,
            },
            "ab": {
                "enable": 0,
                "duration_sec": 0,
                "total_conn": 2000,
                "concurrent_conn": 100,
                "target_urls": ["http://192.168.15.17/"],
            },
            "ftp": {
                "enable": 1,
                "target_ip": "127.0.0.1",
                "target_port": 21,
                "user": "test",
                "password": "password",
                "file_size_mb": 10,
                "duration_sec": 0,
                "count": 10,
                "concurrent_conn": 5,
            },
            "ftps": {
                "enable": 0,
                "target_ip": "127.0.0.1",
                "target_port": 990,
                "user": "test",
                "password": "password",
                "file_size_mb": 10,
                "duration_sec": 0,
                "count": 10,
                "concurrent_conn": 5,
            },
            "sftp": {
                "enable": 0,
                "target_ip": "127.0.0.1",
                "target_port": 2222,
                "user": "test",
                "password": "password",
                "file_size_mb": 10,
                "duration_sec": 0,
                "count": 10,
                "concurrent_conn": 5,
            },
        },
    }


@pytest.fixture
def tmp_config_dir(tmp_path, minimal_config):
    config_path = tmp_path / "config.json"
    state_path = tmp_path / "state.json"
    config_path.write_text(
        json.dumps(minimal_config), encoding="utf-8"
    )
    state_path.write_text(
        json.dumps({"cur_iter": 0, "cur_log_dir": ""}),
        encoding="utf-8",
    )
    return tmp_path
