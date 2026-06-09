import json
import os
import logging
import random
import threading
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from stress_test import (
    StressTest, MainThreadIterFilter, ITER_FILTER,
    RESOURCE_MONITOR_INTERVAL
)
from util_config import AgentConfigManager


@pytest.fixture
def config_mgr(mock_env):
    mgr = MagicMock(spec=AgentConfigManager)
    mgr.is_64bit = True
    mgr.is_local_cfg = False
    mgr.failclose_active = False
    mgr.is_false_close = False
    mgr.check_watchdog_mode.return_value = False
    mgr.get_tenant_hostname.return_value = "tenant.example.com"
    mgr.setup_environment.return_value = True
    mgr.url_in_nsexception.return_value = False
    mgr.load_nsexception.return_value = None
    mgr.restore_config.return_value = None
    mgr.toggle_failclose.return_value = None
    mgr.toggle_on_off_prem.return_value = False
    return mgr


@pytest.fixture
def url_file(tmp_path):
    f = tmp_path / "data" / "url.txt"
    f.parent.mkdir(parents=True, exist_ok=True)
    urls = [f"https://site{i}.com" for i in range(100)]
    f.write_text("\n".join(urls), encoding="utf-8")
    return f


@pytest.fixture
def st(
    tmp_path, mock_power_mgr, mock_svc_mgr, mock_sys_info,
    mock_input_mon, mock_diag, config_mgr
):
    log_dir = str(tmp_path / "log")
    os.makedirs(log_dir, exist_ok=True)
    obj = StressTest(
        log_dir=log_dir,
        power_mgr=mock_power_mgr,
        svc_mgr=mock_svc_mgr,
        sys_info=mock_sys_info,
        input_mon=mock_input_mon,
        diag=mock_diag,
        config_mgr=config_mgr,
    )
    return obj


class TestMainThreadIterFilter:
    def test_filter_adds_iteration(self):
        f = MainThreadIterFilter()
        f.iteration = 5
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "hello", (), None
        )
        result = f.filter(record)
        assert result is True
        assert record.msg.startswith("[5]")

    def test_filter_none_iteration(self):
        f = MainThreadIterFilter()
        f.iteration = None
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "hello", (), None
        )
        result = f.filter(record)
        assert result is True
        assert record.msg == "hello"


class TestStressTestInit:
    def test_dependencies_stored(self, st, mock_power_mgr, mock_svc_mgr):
        assert st.power is mock_power_mgr
        assert st.service is mock_svc_mgr
        assert st.stop_event is not None
        assert isinstance(st.stop_event, threading.Event)

    def test_default_state(self, st):
        assert st.urls == []
        assert st.url_cursor == 0
        assert st.total_zero_dumps == 0
        assert st.client_thread is None
        assert st.resource_monitor_thread is None
        assert st.validation_enabled is False
        assert st.reboot_pending is False
        assert st.is_continue_mode is False
        assert st.webui_client is None
        assert st.current_protocol == "tls"
        assert st.current_steering_mode == "web"
        assert st.current_webui_failclose is False
        assert st.current_sni is False
        assert st.current_exception_domains_added is False
        assert st.current_webui_client_disabling is False
        assert st.current_custom_ports_added is False
        assert st.current_interop_proxy is False
        assert st.mtu_index == 0

    def test_service_names_set(self, st):
        assert st.service_name != ""
        assert st.drv_name == "stadrv"
        assert st.service_process_name != ""


class TestResourceMonitor:
    def test_starts_thread(self, st):
        st.start_resource_monitor()
        assert st.resource_monitor_thread is not None
        assert st.resource_monitor_thread.is_alive()
        st.stop_event.set()
        st.resource_monitor_thread.join(timeout=2)

    def test_calls_log_process_usage(self, st, mock_sys_info):
        def _stop_after_call(*args, **kwargs):
            st.stop_event.set()
            return True
        mock_sys_info.log_process_usage.side_effect = _stop_after_call
        st._resource_monitor_loop()
        mock_sys_info.log_process_usage.assert_called_with(
            st.service_process_name, st.log_dir
        )

    def test_handles_exception(self, st, mock_sys_info):
        def _stop_after_call(*args, **kwargs):
            st.stop_event.set()
            raise Exception("fail")
        mock_sys_info.log_process_usage.side_effect = _stop_after_call
        st._resource_monitor_loop()

    def test_constant_is_60(self):
        assert RESOURCE_MONITOR_INTERVAL == 60


class TestLoadUrls:
    def test_loads_urls(self, st, url_file):
        st.url_file = str(url_file)
        st.load_urls()
        assert len(st.urls) == 100

    def test_strips_trailing_slash(self, tmp_path, st):
        f = tmp_path / "urls.txt"
        f.write_text(
            "https://a.com/\nhttps://b.com/\n", encoding="utf-8"
        )
        st.url_file = str(f)
        st.load_urls()
        assert "https://a.com" in st.urls
        assert "https://b.com" in st.urls

    def test_missing_file(self, st):
        st.url_file = "nonexistent_file.txt"
        st.load_urls()
        assert st.urls == []

    def test_shuffles(self, st, url_file):
        st.url_file = str(url_file)
        st.load_urls()
        urls_sorted = sorted(st.urls)
        assert st.urls != urls_sorted or len(st.urls) <= 1


class TestGetNextBatch:
    def test_returns_batch_size(self, st, url_file):
        st.url_file = str(url_file)
        st.load_urls()
        batch = st.get_next_batch(10)
        assert len(batch) == 10

    def test_empty_urls(self, st):
        assert st.get_next_batch(10) == []

    def test_cursor_advances(self, st, url_file):
        st.url_file = str(url_file)
        st.load_urls()
        batch1 = st.get_next_batch(10)
        batch2 = st.get_next_batch(10)
        assert batch1 != batch2 or len(st.urls) <= 10

    def test_wraps_around(self, st, url_file):
        st.url_file = str(url_file)
        st.load_urls()
        for _ in range(15):
            batch = st.get_next_batch(10)
            assert len(batch) == 10

    def test_small_url_list(self, st):
        st.urls = ["https://a.com", "https://b.com"]
        batch = st.get_next_batch(50)
        assert len(batch) == 2

    def test_exact_size_batch(self, st):
        st.urls = [f"https://s{i}.com" for i in range(10)]
        batch = st.get_next_batch(10)
        assert len(batch) == 10


class TestHeaderMsg:
    def test_no_crash(self, st):
        st.config.load = MagicMock()
        st.config.loop_times = 10
        st.config.stop_svc_interval = 1
        st.config.reboot_interval = 0
        st.config.aoac_s0_standby_enabled = False
        st.header_msg()

class TestSetup:
    @patch("stress_test.sys.platform", "win32")
    def test_returns_false_when_environment_setup_fails(
        self, st, config_mgr, mock_diag, mock_sys_info
    ):
        st.config.load = MagicMock()
        st.config.aoac_s4_hibernate_enabled = False
        st.config.aoac_s1_standby_enabled = False
        st.config.browser_log_validation = 0
        st.config.curl_flood_log_validation = 0
        st.config.config_data = {"client_feature_toggling": {}}
        st.config.aoac_s0_standby_enabled = False
        st.load_urls = MagicMock()

        config_mgr.setup_environment.return_value = False
        config_mgr.last_setup_error = (
            "Service 'stAgentSvc' not found. Client not installed."
        )

        result = st.setup()

        assert result is False
        assert st.stop_event.is_set() is True
        config_mgr.restore_config.assert_called_once_with(remove_only=False)
        mock_diag.enable_client_tracing.assert_not_called()
        mock_sys_info.remove_startup_task.assert_not_called()


class TestRun:
    def test_skips_run_when_already_finished_all_iterations(
        self, st, mock_input_mon
    ):
        st.config.loop_times = 200
        st.config.cur_iter = 200
        st.is_continue_mode = True
        st.config.reboot_interval = 0

        with patch("stress_test.logger") as mock_logger:
            st.run()
            calls = [str(c) for c in mock_logger.info.call_args_list]
            run_calls = [c for c in calls if "Already completed" in c or
                        "Finished 200 iterations" in c]
            assert len(run_calls) >= 1
            mock_input_mon.stop_input_monitor.assert_called_once()

class TestExecStartService:
    def test_already_running(self, st, mock_svc_mgr):
        mock_svc_mgr.get_service_status.return_value = "RUNNING"
        st.exec_start_service()
        mock_svc_mgr.start_service.assert_not_called()

    def test_not_running_starts(self, st, mock_svc_mgr, mock_diag):
        mock_svc_mgr.get_service_status.return_value = "STOPPED"
        st.config.client_disabling_enabled = False
        st.stop_event.set()
        st.exec_start_service()
        mock_svc_mgr.start_service.assert_called_once()

    def test_not_found_sets_stop(self, st, mock_svc_mgr):
        mock_svc_mgr.get_service_status.return_value = "NOT_FOUND"
        st.exec_start_service()
        assert st.stop_event.is_set()


class TestExecStopService:
    def test_running_stops(self, st, mock_svc_mgr):
        st.is_watchdog_mode = False
        mock_svc_mgr.get_service_status.return_value = "RUNNING"
        mock_svc_mgr.stop_service.return_value = True
        st.stop_event.set()
        st.exec_stop_service()
        mock_svc_mgr.stop_service.assert_called()

    def test_not_found_sets_stop(self, st, mock_svc_mgr):
        mock_svc_mgr.get_service_status.return_value = "NOT_FOUND"
        st.exec_stop_service()
        assert st.stop_event.is_set()

    def test_stop_fails_handles_non_stop(self, st, mock_svc_mgr):
        st.is_watchdog_mode = False
        mock_svc_mgr.get_service_status.return_value = "RUNNING"
        mock_svc_mgr.stop_service.return_value = False
        st.exec_stop_service()
        mock_svc_mgr.handle_non_stop.assert_called_once()
        assert st.stop_event.is_set()


class TestExecBrowserTabs:
    @patch("stress_test.util_traffic.open_browser_tabs", return_value=["u1"])
    def test_opens_when_enabled(self, mock_open, st):
        st.config.enable_browser_tabs_open = 1
        result = st.exec_browser_tabs(["https://a.com"])
        assert result == ["u1"]
        mock_open.assert_called_once()

    def test_disabled_returns_empty(self, st):
        st.config.enable_browser_tabs_open = 0
        result = st.exec_browser_tabs(["https://a.com"])
        assert result == []


class TestExecCurlRequests:
    @patch("stress_test.util_traffic.curl_requests")
    def test_calls_curl(self, mock_curl, st):
        st.urls = ["https://a.com"]
        st.exec_curl_requests()
        mock_curl.assert_called_once_with(st.urls, st.stop_event)


class TestExecValidationChecks:
    def test_disabled_returns_true(self, st):
        st.validation_enabled = False
        assert st.exec_validation_checks({}) is True

    @patch("stress_test.util_validate.validate_traffic_flow", return_value=True)
    def test_enabled_calls_validate(self, mock_validate, st):
        st.validation_enabled = True
        st.config.browser_log_validation = 1
        st.config.curl_flood_log_validation = 0
        st.config.client_disabling_enabled = False
        result = st.exec_validation_checks({"msedge.exe": ["u1"]})
        assert result is True
        mock_validate.assert_called_once()

    def test_skipped_when_client_disabled(self, st):
        st.validation_enabled = True
        st.config.browser_log_validation = 1
        st.config.curl_flood_log_validation = 0
        st.config.client_disabling_enabled = True
        st.client_enabled_event.clear()
        assert st.exec_validation_checks({}) is True


class TestExecOnOffPrem:
    def test_disabled(self, st):
        st.config.config_data = {"client_feature_toggling": {}}
        assert st.exec_on_off_prem(1) is False

    def test_enabled_calls_toggle(self, st, config_mgr):
        st.config.config_data = {
            "client_feature_toggling": {
                "webui_on_prem": {
                    "enable": 1,
                    "onprem_http_host": "http://host.com",
                }
            }
        }
        config_mgr.toggle_on_off_prem.return_value = True
        assert st.exec_on_off_prem(1) is True
        config_mgr.toggle_on_off_prem.assert_called_once()


class TestExecTlsDtlsToggle:
    def test_disabled(self, st):
        st.config.tls_dtls_toggle_enabled = False
        assert st.exec_tls_dtls_toggle(5) is False

    def test_interval_zero(self, st):
        st.config.tls_dtls_toggle_enabled = True
        st.config.tls_dtls_toggle_interval = 0
        assert st.exec_tls_dtls_toggle(5) is False

    def test_not_on_interval(self, st):
        st.config.tls_dtls_toggle_enabled = True
        st.config.tls_dtls_toggle_interval = 5
        st.webui_client = MagicMock()
        assert st.exec_tls_dtls_toggle(3) is False

    def test_no_client(self, st):
        st.config.tls_dtls_toggle_enabled = True
        st.config.tls_dtls_toggle_interval = 5
        st.webui_client = None
        assert st.exec_tls_dtls_toggle(5) is False

    def test_toggle_tls_to_dtls(self, st):
        st.config.tls_dtls_toggle_enabled = True
        st.config.tls_dtls_toggle_interval = 5
        st.webui_client = MagicMock()
        st.webui_client.toggle_tls_dtls.return_value = True
        st.current_protocol = "tls"
        assert st.exec_tls_dtls_toggle(5) is True
        st.webui_client.toggle_tls_dtls.assert_called_once_with(True)
        assert st.current_protocol == "dtls"

    def test_toggle_dtls_to_tls(self, st):
        st.config.tls_dtls_toggle_enabled = True
        st.config.tls_dtls_toggle_interval = 5
        st.webui_client = MagicMock()
        st.webui_client.toggle_tls_dtls.return_value = True
        st.current_protocol = "dtls"
        assert st.exec_tls_dtls_toggle(10) is True
        st.webui_client.toggle_tls_dtls.assert_called_once_with(False)
        assert st.current_protocol == "tls"

    def test_toggle_failure(self, st):
        st.config.tls_dtls_toggle_enabled = True
        st.config.tls_dtls_toggle_interval = 5
        st.webui_client = MagicMock()
        st.webui_client.toggle_tls_dtls.return_value = False
        st.current_protocol = "tls"
        assert st.exec_tls_dtls_toggle(5) is False
        assert st.current_protocol == "tls"


class TestExecSteeringModeToggle:
    def test_disabled(self, st):
        st.config.steering_mode_toggle_enabled = False
        assert st.exec_steering_mode_toggle(10) is False

    def test_not_on_interval(self, st):
        st.config.steering_mode_toggle_enabled = True
        st.config.steering_mode_toggle_interval = 10
        st.webui_client = MagicMock()
        assert st.exec_steering_mode_toggle(3) is False

    def test_toggle_web_to_all(self, st):
        st.config.steering_mode_toggle_enabled = True
        st.config.steering_mode_toggle_interval = 10
        st.webui_client = MagicMock()
        st.webui_client.toggle_steering_mode.return_value = True
        st.current_steering_mode = "web"
        assert st.exec_steering_mode_toggle(10) is True
        st.webui_client.toggle_steering_mode.assert_called_once_with(True)
        assert st.current_steering_mode == "all"

    def test_toggle_all_to_web(self, st):
        st.config.steering_mode_toggle_enabled = True
        st.config.steering_mode_toggle_interval = 10
        st.webui_client = MagicMock()
        st.webui_client.toggle_steering_mode.return_value = True
        st.current_steering_mode = "all"
        assert st.exec_steering_mode_toggle(10) is True
        st.webui_client.toggle_steering_mode.assert_called_once_with(False)
        assert st.current_steering_mode == "web"

    def test_toggle_failure(self, st):
        st.config.steering_mode_toggle_enabled = True
        st.config.steering_mode_toggle_interval = 10
        st.webui_client = MagicMock()
        st.webui_client.toggle_steering_mode.return_value = False
        st.current_steering_mode = "web"
        assert st.exec_steering_mode_toggle(10) is False
        assert st.current_steering_mode == "web"


class TestExecWebuiFailcloseToggle:
    def test_disabled(self, st):
        st.config.webui_failclose_toggle_enabled = False
        assert st.exec_webui_failclose_toggle(15) is False

    def test_toggle_on(self, st):
        st.config.webui_failclose_toggle_enabled = True
        st.config.webui_failclose_toggle_interval = 15
        st.webui_client = MagicMock()
        st.webui_client.toggle_webui_failclose.return_value = True
        st.current_webui_failclose = False
        assert st.exec_webui_failclose_toggle(15) is True
        st.webui_client.toggle_webui_failclose.assert_called_once_with(True)
        assert st.current_webui_failclose is True

    def test_toggle_off(self, st):
        st.config.webui_failclose_toggle_enabled = True
        st.config.webui_failclose_toggle_interval = 15
        st.webui_client = MagicMock()
        st.webui_client.toggle_webui_failclose.return_value = True
        st.current_webui_failclose = True
        assert st.exec_webui_failclose_toggle(15) is True
        st.webui_client.toggle_webui_failclose.assert_called_once_with(False)
        assert st.current_webui_failclose is False

    def test_toggle_failure(self, st):
        st.config.webui_failclose_toggle_enabled = True
        st.config.webui_failclose_toggle_interval = 15
        st.webui_client = MagicMock()
        st.webui_client.toggle_webui_failclose.return_value = False
        st.current_webui_failclose = False
        assert st.exec_webui_failclose_toggle(15) is False
        assert st.current_webui_failclose is False


class TestExecSniToggle:
    def test_disabled(self, st):
        st.config.sni_toggle_enabled = False
        assert st.exec_sni_toggle(20) is False

    def test_toggle_on(self, st):
        st.config.sni_toggle_enabled = True
        st.config.sni_toggle_interval = 20
        st.webui_client = MagicMock()
        st.webui_client.toggle_sni_check.return_value = True
        st.current_sni = False
        assert st.exec_sni_toggle(20) is True
        st.webui_client.toggle_sni_check.assert_called_once_with(True)
        assert st.current_sni is True

    def test_toggle_off(self, st):
        st.config.sni_toggle_enabled = True
        st.config.sni_toggle_interval = 20
        st.webui_client = MagicMock()
        st.webui_client.toggle_sni_check.return_value = True
        st.current_sni = True
        assert st.exec_sni_toggle(20) is True
        st.webui_client.toggle_sni_check.assert_called_once_with(False)
        assert st.current_sni is False

    def test_toggle_failure(self, st):
        st.config.sni_toggle_enabled = True
        st.config.sni_toggle_interval = 20
        st.webui_client = MagicMock()
        st.webui_client.toggle_sni_check.return_value = False
        st.current_sni = False
        assert st.exec_sni_toggle(20) is False
        assert st.current_sni is False


class TestExecExceptionDomainsToggle:
    def test_disabled(self, st):
        st.config.exception_domains_toggle_enabled = False
        assert st.exec_exception_domains_toggle(10) is False

    def test_no_domains(self, st):
        st.config.exception_domains_toggle_enabled = True
        st.config.exception_domains_toggle_interval = 10
        st.config.exception_domains_list = []
        st.webui_client = MagicMock()
        assert st.exec_exception_domains_toggle(10) is False

    def test_add_domains(self, st):
        st.config.exception_domains_toggle_enabled = True
        st.config.exception_domains_toggle_interval = 10
        st.config.exception_domains_list = ["a.com"]
        st.webui_client = MagicMock()
        st.webui_client.toggle_exception_domains.return_value = True
        st.current_exception_domains_added = False
        assert st.exec_exception_domains_toggle(10) is True
        st.webui_client.toggle_exception_domains.assert_called_once_with(
            True, ["a.com"]
        )
        assert st.current_exception_domains_added is True

    def test_remove_domains(self, st):
        st.config.exception_domains_toggle_enabled = True
        st.config.exception_domains_toggle_interval = 10
        st.config.exception_domains_list = ["a.com"]
        st.webui_client = MagicMock()
        st.webui_client.toggle_exception_domains.return_value = True
        st.current_exception_domains_added = True
        assert st.exec_exception_domains_toggle(10) is True
        st.webui_client.toggle_exception_domains.assert_called_once_with(
            False, ["a.com"]
        )
        assert st.current_exception_domains_added is False

    def test_failure(self, st):
        st.config.exception_domains_toggle_enabled = True
        st.config.exception_domains_toggle_interval = 10
        st.config.exception_domains_list = ["a.com"]
        st.webui_client = MagicMock()
        st.webui_client.toggle_exception_domains.return_value = False
        st.current_exception_domains_added = False
        assert st.exec_exception_domains_toggle(10) is False
        assert st.current_exception_domains_added is False


class TestExecWebuiClientDisablingToggle:
    def test_disabled(self, st):
        st.config.webui_client_disabling_toggle_enabled = False
        assert st.exec_webui_client_disabling_toggle(10) is False

    def test_toggle_on(self, st):
        st.config.webui_client_disabling_toggle_enabled = True
        st.config.webui_client_disabling_toggle_interval = 10
        st.webui_client = MagicMock()
        st.webui_client.toggle_client_disabling.return_value = True
        st.current_webui_client_disabling = False
        assert st.exec_webui_client_disabling_toggle(10) is True
        st.webui_client.toggle_client_disabling.assert_called_once_with(True)
        assert st.current_webui_client_disabling is True

    def test_toggle_off(self, st):
        st.config.webui_client_disabling_toggle_enabled = True
        st.config.webui_client_disabling_toggle_interval = 10
        st.webui_client = MagicMock()
        st.webui_client.toggle_client_disabling.return_value = True
        st.current_webui_client_disabling = True
        assert st.exec_webui_client_disabling_toggle(10) is True
        st.webui_client.toggle_client_disabling.assert_called_once_with(False)
        assert st.current_webui_client_disabling is False

    def test_failure(self, st):
        st.config.webui_client_disabling_toggle_enabled = True
        st.config.webui_client_disabling_toggle_interval = 10
        st.webui_client = MagicMock()
        st.webui_client.toggle_client_disabling.return_value = False
        st.current_webui_client_disabling = False
        assert st.exec_webui_client_disabling_toggle(10) is False
        assert st.current_webui_client_disabling is False


class TestExecCustomPortsToggle:
    def test_disabled(self, st):
        st.config.custom_ports_toggle_enabled = False
        assert st.exec_custom_ports_toggle(10) is False

    def test_no_ports(self, st):
        st.config.custom_ports_toggle_enabled = True
        st.config.custom_ports_toggle_interval = 10
        st.config.custom_ports_list = []
        st.webui_client = MagicMock()
        assert st.exec_custom_ports_toggle(10) is False

    def test_add_ports(self, st):
        st.config.custom_ports_toggle_enabled = True
        st.config.custom_ports_toggle_interval = 10
        st.config.custom_ports_list = [{"ports": "9501"}]
        st.webui_client = MagicMock()
        st.webui_client.toggle_custom_ports.return_value = True
        st.current_custom_ports_added = False
        assert st.exec_custom_ports_toggle(10) is True
        st.webui_client.toggle_custom_ports.assert_called_once_with(
            True, [{"ports": "9501"}]
        )
        assert st.current_custom_ports_added is True

    def test_remove_ports(self, st):
        st.config.custom_ports_toggle_enabled = True
        st.config.custom_ports_toggle_interval = 10
        st.config.custom_ports_list = [{"ports": "9501"}]
        st.webui_client = MagicMock()
        st.webui_client.toggle_custom_ports.return_value = True
        st.current_custom_ports_added = True
        assert st.exec_custom_ports_toggle(10) is True
        st.webui_client.toggle_custom_ports.assert_called_once_with(
            False, [{"ports": "9501"}]
        )
        assert st.current_custom_ports_added is False

    def test_failure(self, st):
        st.config.custom_ports_toggle_enabled = True
        st.config.custom_ports_toggle_interval = 10
        st.config.custom_ports_list = [{"ports": "9501"}]
        st.webui_client = MagicMock()
        st.webui_client.toggle_custom_ports.return_value = False
        st.current_custom_ports_added = False
        assert st.exec_custom_ports_toggle(10) is False
        assert st.current_custom_ports_added is False


class TestExecInteropProxyToggle:
    def test_disabled(self, st):
        st.config.interop_proxy_toggle_enabled = False
        assert st.exec_interop_proxy_toggle(10) is False

    def test_toggle_on(self, st):
        st.config.interop_proxy_toggle_enabled = True
        st.config.interop_proxy_toggle_interval = 10
        st.config.interop_proxy_host = "proxy.com"
        st.config.interop_proxy_port = 8080
        st.webui_client = MagicMock()
        st.webui_client.toggle_interop_proxy.return_value = True
        st.current_interop_proxy = False
        assert st.exec_interop_proxy_toggle(10) is True
        st.webui_client.toggle_interop_proxy.assert_called_once_with(
            True, "proxy.com", 8080
        )
        assert st.current_interop_proxy is True

    def test_toggle_off(self, st):
        st.config.interop_proxy_toggle_enabled = True
        st.config.interop_proxy_toggle_interval = 10
        st.config.interop_proxy_host = "proxy.com"
        st.config.interop_proxy_port = 8080
        st.webui_client = MagicMock()
        st.webui_client.toggle_interop_proxy.return_value = True
        st.current_interop_proxy = True
        assert st.exec_interop_proxy_toggle(10) is True
        st.webui_client.toggle_interop_proxy.assert_called_once_with(
            False, "proxy.com", 8080
        )
        assert st.current_interop_proxy is False

    def test_failure(self, st):
        st.config.interop_proxy_toggle_enabled = True
        st.config.interop_proxy_toggle_interval = 10
        st.config.interop_proxy_host = ""
        st.config.interop_proxy_port = 0
        st.webui_client = MagicMock()
        st.webui_client.toggle_interop_proxy.return_value = False
        st.current_interop_proxy = False
        assert st.exec_interop_proxy_toggle(10) is False
        assert st.current_interop_proxy is False


class TestExecMtuToggle:
    def test_disabled(self, st):
        st.config.mtu_toggle_enabled = False
        assert st.exec_mtu_toggle(10) is False

    def test_cycles_values(self, st):
        st.config.mtu_toggle_enabled = True
        st.config.mtu_toggle_interval = 10
        st.config.mtu_values = [1400, 800, ""]
        st.webui_client = MagicMock()
        st.webui_client.set_mtu.return_value = True
        st.mtu_index = 0
        assert st.exec_mtu_toggle(10) is True
        st.webui_client.set_mtu.assert_called_with(1400)
        assert st.mtu_index == 1

        assert st.exec_mtu_toggle(20) is True
        st.webui_client.set_mtu.assert_called_with(800)
        assert st.mtu_index == 2

        assert st.exec_mtu_toggle(30) is True
        st.webui_client.set_mtu.assert_called_with("")
        assert st.mtu_index == 3

    def test_wraps_around(self, st):
        st.config.mtu_toggle_enabled = True
        st.config.mtu_toggle_interval = 10
        st.config.mtu_values = [1400, 800]
        st.webui_client = MagicMock()
        st.webui_client.set_mtu.return_value = True
        st.mtu_index = 2
        assert st.exec_mtu_toggle(10) is True
        st.webui_client.set_mtu.assert_called_with(1400)
        assert st.mtu_index == 3

    def test_failure(self, st):
        st.config.mtu_toggle_enabled = True
        st.config.mtu_toggle_interval = 10
        st.config.mtu_values = [1400, 800]
        st.webui_client = MagicMock()
        st.webui_client.set_mtu.return_value = False
        st.mtu_index = 0
        assert st.exec_mtu_toggle(10) is False
        assert st.mtu_index == 0


class TestTearDown:
    def test_restores_config(self, st, config_mgr, mock_sys_info):
        st.config.reboot_interval = 0
        st.tear_down()
        config_mgr.restore_config.assert_called_once()

    def test_cleans_reboot_task(self, st, config_mgr, mock_sys_info):
        st.config.reboot_interval = 5
        st.reboot_pending = False
        st.tear_down()
        mock_sys_info.remove_startup_task.assert_called_once_with(
            "StressTestAutoResume"
        )

    def test_keeps_task_when_reboot_pending(self, st, mock_sys_info):
        st.config.reboot_interval = 5
        st.reboot_pending = True
        st.tear_down()
        mock_sys_info.remove_startup_task.assert_not_called()


class TestRunSingleIteration:
    @patch("stress_test.util_validate")
    @patch("stress_test.util_traffic")
    @patch("stress_test.smart_sleep", return_value=False)
    def test_one_iter_completes(
        self, mock_sleep, mock_traffic, mock_validate,
        st, mock_svc_mgr, mock_diag, url_file
    ):
        st.url_file = str(url_file)
        st.load_urls()
        st.config.loop_times = 1
        st.config.stop_svc_interval = 0
        st.config.stop_drv_interval = 0
        st.config.reboot_interval = 0
        st.config.failclose_enabled = False
        st.config.failclose_interval = 0
        st.config.tls_dtls_toggle_enabled = False
        st.config.steering_mode_toggle_enabled = False
        st.config.webui_failclose_toggle_enabled = False
        st.config.sni_toggle_enabled = False
        st.config.exception_domains_toggle_enabled = False
        st.config.webui_client_disabling_toggle_enabled = False
        st.config.custom_ports_toggle_enabled = False
        st.config.interop_proxy_toggle_enabled = False
        st.config.mtu_toggle_enabled = False
        st.config.client_disabling_enabled = False
        st.config.enable_browser_tabs_open = 0
        st.config.dns_enabled = False
        st.config.curl_flood_enabled = False
        st.config.aoac_s0_standby_enabled = False
        st.config.aoac_s1_standby_enabled = False
        st.config.aoac_s4_hibernate_enabled = False
        st.config.long_idle_interval = 0
        st.config.browser_log_validation = 0
        st.config.curl_flood_log_validation = 0
        st.config.config_data = {}

        mock_svc_mgr.get_service_status.return_value = "RUNNING"
        mock_diag.check_crash_dumps.return_value = (False, 0)

        st.run()
        mock_svc_mgr.get_service_status.assert_called()
