import sys
import os
import json
import random
import threading
import logging
import subprocess
from urllib.parse import urlparse
import time

# Interfaces
from interfaces.i_power import IPowerManager
from interfaces.i_service import IServiceManager
from interfaces.i_system import ISystemInfo
from interfaces.i_input import IInputMonitor
from interfaces.i_diag import IDiagnostics

# Utilities (Shared)
from util_log import LogSetup
from util_time import smart_sleep
from util_config import AgentConfigManager
from util_tool_config import ToolConfig
import util_traffic
import util_client
import util_validate

TINY_SEC = 5
SHORT_SEC = 15
STD_SEC = 30
LONG_SEC = 60
BATCH_SIZE = 50
RESOURCE_MONITOR_INTERVAL = 60

class MainThreadIterFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.iteration = None

    def filter(self, record):
        if self.iteration is not None:
             if threading.current_thread() is threading.main_thread():
                 record.msg = f"[{self.iteration}] {record.msg}"
        return True

ITER_FILTER = MainThreadIterFilter()
logger = logging.getLogger()

class StressTest:
    def __init__(
        self, 
        log_dir: str, 
        power_mgr: IPowerManager,
        svc_mgr: IServiceManager,
        sys_info: ISystemInfo,
        input_mon: IInputMonitor,
        diag: IDiagnostics,
        config_mgr: AgentConfigManager,
        is_continue_mode: bool = False
    ):
        self.log_dir = log_dir
        self.power = power_mgr
        self.service = svc_mgr
        self.system = sys_info
        self.input = input_mon
        self.diag = diag
        self.is_continue_mode = is_continue_mode

        self.url_file = os.path.join("data", "url.txt")

        if sys.platform.startswith('darwin'):
            self.service_name = "com.netskope.client.stagentui"
            self.drv_name = "stadrv"
            self.service_process_name = "stAgentSvc"
            self.watchdog_process_name = "stAgentSvcMon"
        elif sys.platform.startswith('linux'):
            self.service_name = "stagentd.service"
            self.drv_name = "stadrv"
            self.service_process_name = "stagentd"
            self.watchdog_process_name = "stagentd-mon"
        else:  # Windows
            self.service_name = "stagentsvc"
            self.drv_name = "stadrv"
            self.service_process_name = "stAgentSvc.exe"
            self.watchdog_process_name = "stAgentSvcMon.exe"

        self.config = ToolConfig(os.path.join("data", "config.json"))

        if sys.platform.startswith("win"):
            self.tool_dir = os.path.join("platforms", "windows", "tool")
            self.manage_nic_script = os.path.join(self.tool_dir, "manage_nic.ps1")
        elif sys.platform.startswith("darwin"):
            self.tool_dir = os.path.join("platforms", "macos", "tool")
        elif sys.platform.startswith("linux"):
            self.tool_dir = os.path.join("platforms", "linux", "tool")
            self.close_browsers_script = os.path.join(self.tool_dir, "close_browsers.sh")

        self.cfg_mgr = config_mgr
        self.stop_event = threading.Event()

        self.urls = []
        self.url_cursor = 0
        self.total_zero_dumps = 0
        self.client_thread = None
        self.resource_monitor_thread = None
        self.validation_enabled = False
        self.client_enabled_event = threading.Event()
        self.client_enabled_event.set()
        self.last_svc_restart_count = 0
        self.reboot_pending = False
        self.cur_svc_status = "UNKNOWN"
        self.is_watchdog_mode = False
        self.webui_client = None
        self.current_protocol = "tls"
        self.current_steering_mode = "web"
        self.current_webui_failclose = False
        self.current_sni = False
        self.current_exception_domains_added = False
        self.current_webui_client_disabling = False
        self.current_custom_ports_added = False
        self.current_interop_proxy = False
        self.mtu_index = 0

    def _disable_all_webui_toggles(self):
        self.config.tls_dtls_toggle_enabled = False
        self.config.steering_mode_toggle_enabled = False
        self.config.webui_failclose_toggle_enabled = False
        self.config.sni_toggle_enabled = False
        self.config.exception_domains_toggle_enabled = False
        self.config.webui_client_disabling_toggle_enabled = False
        self.config.custom_ports_toggle_enabled = False
        self.config.interop_proxy_toggle_enabled = False
        self.config.mtu_toggle_enabled = False
        self.webui_client = None

    def setup(self):
        if sys.platform == "win32":
            for priv in ["SeDebugPrivilege",
                         "SeSystemtimePrivilege",
                         "SeWakeAlarmPrivilege"]:
                err = self.system.enable_privilege(priv)
                if err != 0:
                    logger.warning(f"Failed to enable {priv}. Err: {err}")

        self.config.load()

        if self.config.decouple_client:
            logger.info("Decouple mode enabled. Skipping all client interactions.")
            self.validation_enabled = False
            self.load_urls()
            return True

        if self.config.aoac_s4_hibernate_enabled:
            if not self.power.is_sleep_state_available("Hibernate"):
                logger.warning(
                    "AOAC S4 (Hibernate) is disabled due to system not supporting it.")
                self.config.aoac_s4_hibernate_enabled = False

        if self.config.aoac_s1_standby_enabled:
            if not self.power.is_sleep_state_available("Standby (S1)"):
                logger.warning(
                    "AOAC S1 (Standby) is disabled due to system not supporting it.")
                self.config.aoac_s1_standby_enabled = False

        if self.config.browser_log_validation != 0 or self.config.curl_flood_log_validation != 0:
            self.cfg_mgr.load_nsexception()

        tenant_host = self.cfg_mgr.get_tenant_hostname()
        client_toggles = self.config.config_data.get("client_feature_toggling", {})
        webui_on_prem = client_toggles.get("webui_on_prem", {})
        webui_login = client_toggles.get("webui_login", {})
        onprem_enabled = webui_on_prem.get("enable", 0)
        any_webui_toggle = (
            self.config.tls_dtls_toggle_enabled
            or self.config.steering_mode_toggle_enabled
            or self.config.webui_failclose_toggle_enabled
            or self.config.sni_toggle_enabled
            or self.config.exception_domains_toggle_enabled
            or self.config.webui_client_disabling_toggle_enabled
            or self.config.custom_ports_toggle_enabled
            or self.config.interop_proxy_toggle_enabled
            or self.config.mtu_toggle_enabled
        )

        if onprem_enabled or any_webui_toggle:
            try:
                import getpass
                print("\nWebUI feature enabled. Please enter tenant password below.")
                password = getpass.getpass("Tenant Password: ")
                import util_webui

                if onprem_enabled:
                    util_webui.perform_onprem_setup(
                        self.config.config_data, tenant_host, password
                    )

                if any_webui_toggle:
                    hostname = webui_login.get("tenant_hostname", "") or tenant_host
                    username = webui_login.get("tenant_username", "")
                    if hostname and username:
                        self.webui_client = util_webui.WebUIClient(
                            hostname, username, password
                        )
                        if not self.webui_client.login():
                            logger.warning(
                                "WebUI login failed. WebUI toggles disabled."
                            )
                            self._disable_all_webui_toggles()
                        else:
                            self.webui_client.load_config_names_from_local(
                                self.cfg_mgr.stagent_root
                            )
                    else:
                        logger.error(
                            "Missing tenant_hostname or tenant_username. "
                            "WebUI toggles disabled."
                        )
                        self._disable_all_webui_toggles()
            except ImportError:
                logger.error(
                    "Failed to load WebUI dependencies. "
                    "Please ensure 'pylark-webapi-lib' is installed/configured."
                )
            except Exception as e:
                logger.warning(f"Failed to read password or setup WebUI: {e}")
        else:
            logger.info("WebUI features disabled.")

        self.load_urls()

        if self.config.browser_log_validation or self.config.curl_flood_log_validation:
            st_cfg = util_validate.get_steering_config()
            if not st_cfg:
                logger.warning("Steering config empty/not found. Validation disabled.")

            mode = st_cfg.get("firewall_traffic_mode") if st_cfg else None
            if not mode and st_cfg:
                mode = st_cfg.get("traffic_mode")

            if mode == "all" or mode == "web":
                self.validation_enabled = True
                logger.info(f"Validation Enabled. Mode: {mode}")
                util_validate.get_validator().update_pos_with_time_buffer(10)
            else:
                logger.info(f"Validation Disabled. Mode: '{mode}'")
        else:
            logger.info("Validation Disabled.")

        if (
            self.config.aoac_s0_standby_enabled or 
            self.config.aoac_s1_standby_enabled or
            self.config.aoac_s4_hibernate_enabled
        ):
            self.power.enable_wake_timers()

        if sys.platform.startswith("win"):
            # Ensure any previous state is cleaned up first
            self.cfg_mgr.restore_config(remove_only=False)

            if not self.cfg_mgr.setup_environment():
                reason = getattr(self.cfg_mgr, "last_setup_error", "")
                if reason:
                    logger.error(f"Environment setup aborted: {reason}")
                else:
                    logger.error("Environment setup aborted.")
                self.stop_event.set()
                return False

        self.is_watchdog_mode = self.cfg_mgr.check_watchdog_mode()
        if self.is_watchdog_mode:
            logger.info("Watchdog Monitor Mode Detected.")
        
        logger.info("Setup: Ensuring Client is Enabled...")
        self.diag.enable_client_tracing(True, self.cfg_mgr.is_64bit)

        task_name = "StressTestAutoResume"
        self.system.remove_startup_task(task_name)
        
        self.setup_startup_task(task_name)
        return True

    def setup_startup_task(self, task_name):
        if self.config.reboot_interval <= 0:
            return

        py_exe = sys.executable
        script_path = os.path.abspath(sys.modules['__main__'].__file__)

        cmd = f'"{py_exe}" "{script_path}" -continue'
        if sys.platform.startswith("win"):
            if sys.prefix != sys.base_prefix:
                activate_script = os.path.join(sys.prefix, "Scripts", "Activate.ps1")
                if os.path.exists(activate_script):
                    script_dir = os.path.dirname(script_path)
                    cmd = (
                        f'powershell.exe -ExecutionPolicy Bypass -WindowStyle Normal -NoExit -Command '
                        f'"Set-Location \'{script_dir}\'; & \'{activate_script}\'; '
                        f'& \'{py_exe}\' \'{script_path}\' -continue"'
                    )
        elif sys.platform.startswith("darwin"):
            if sys.prefix != sys.base_prefix:
                activate_script = os.path.join(sys.prefix, "bin", "activate")
                if os.path.exists(activate_script):
                    script_dir = os.path.dirname(script_path)
                    cmd = (
                        f'cd "{script_dir}" && . "{activate_script}" && '
                        f'"{py_exe}" "{script_path}" -continue'
                    )

        self.system.set_startup_task(task_name, cmd)

    def tear_down(self):
        if self.config.decouple_client:
            return
        self.cfg_mgr.restore_config()
        if self.config.reboot_interval > 0 and not self.reboot_pending:
            logger.info("Cleaning up reboot task...")
            self.system.remove_startup_task("StressTestAutoResume")

    def load_urls(self):
        try:
            if not os.path.exists(self.url_file):
                logger.error(f"{self.url_file} not found.")
                return
            with open(self.url_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            self.urls = [line.strip().rstrip('/') for line in lines if line.strip()]
            random.shuffle(self.urls)
            logger.info(f"Loaded {len(self.urls)} URLs from {self.url_file}")
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")

    def start_client_thread(self):
        if self.config.decouple_client:
            return
        if self.config.client_disabling_enabled:
            self.client_thread = threading.Thread(
                target=util_client.client_toggler_loop,
                args=(
                    self.stop_event,
                    self.service_name,
                    self.cfg_mgr.is_64bit,
                    self.config.client_enable_min,
                    self.config.client_enable_max,
                    self.config.client_disable_ratio,
                    self.client_enabled_event,
                    self.service,
                    self.diag
                ),
                daemon=True
            )
            self.client_thread.start()

    def start_resource_monitor(self):
        if self.config.decouple_client:
            return
        self.resource_monitor_thread = threading.Thread(
            target=self._resource_monitor_loop,
            daemon=True
        )
        self.resource_monitor_thread.start()
        logger.info(
            f"Resource monitor started ({RESOURCE_MONITOR_INTERVAL}s interval)"
        )

    def _resource_monitor_loop(self):
        while not self.stop_event.is_set():
            try:
                self.system.log_process_usage(
                    self.service_process_name, self.log_dir
                )
            except Exception as e:
                logger.warning(f"Resource monitor error: {e}")
            if self.stop_event.wait(RESOURCE_MONITOR_INTERVAL):
                break

    def exec_failclose_check(self):
        if not self.cfg_mgr.failclose_active:
             logger.info("FailClose simulation not active. Skipping check.")
             return
        logger.info("Checking connection status during FailClose simulation...")
        if smart_sleep(20, self.stop_event): return
        test_urls = random.sample(self.urls, min(len(self.urls), 10))
        logger.info(f"Checking {len(test_urls)} URLs for reachability...")
        for url in test_urls:
            if self.stop_event.is_set(): break
            if util_traffic.check_url_alive(url):
                status = "ALIVE"
            else:
                status = "DEAD (Blocked)"
            logger.info(f"URL: {url} -> {status}")
            if smart_sleep(1, self.stop_event): break
        logger.info("FailClose check done.")
        smart_sleep(SHORT_SEC, self.stop_event)

    def header_msg(self):
        logger.info(f"--------- Start. Total iter: {self.config.loop_times} ---------")
        logger.info(f"Stop svc int: {self.config.stop_svc_interval}")
        logger.info(f"Reboot int: {self.config.reboot_interval}")
        if self.config.aoac_s0_standby_enabled:
            logger.info(f"AOAC S0 Int: {self.config.aoac_s0_standby_interval}")
        logger.info(f"Log Folder: {self.log_dir}")
        logger.info("--> Press ESC or Ctrl+C to stop. <--")
        logger.info("=" * 50)

    def exec_start_service(self):
        status = self.service.get_service_status(self.service_name)
        if status == "NOT_FOUND":
            logger.error(f"Service {self.service_name} NOT FOUND.")
            self.stop_event.set()
            return
        logger.info(f"Current status: {status}")
        if status != "RUNNING":
            started = self.service.start_service(self.service_name)
            if not started:
                logger.error(
                    f"Service '{self.service_name}' failed to reach RUNNING "
                    "state. Stopping test."
                )
                self.stop_event.set()
                return

            logger.info(f"Post-start settle wait for {STD_SEC} seconds")
            if smart_sleep(STD_SEC, self.stop_event): return

            post_status = self.service.get_service_status(self.service_name)
            logger.info(f"Current status (Post-Start): {post_status}")
            if post_status != "RUNNING":
                logger.error(
                    f"Service '{self.service_name}' is not RUNNING after "
                    f"settle wait. Status: {post_status}"
                )
                self.stop_event.set()
                return

            if self.config.client_disabling_enabled:
                logger.info("Service Started. Ensuring Client Enabled.")
                self.diag.enable_client_tracing(True, self.cfg_mgr.is_64bit)

        logger.info(
            f"Collecting resource usage for {self.service_process_name}."
        )
        usage_logged = self.system.log_process_usage(
            self.service_process_name,
            self.log_dir,
        )
        if usage_logged:
            logger.info("Resource usage snapshot collected.")
        else:
            logger.warning(
                f"Resource usage skipped; process '{self.service_process_name}' "
                "was not found."
            )

    def exec_stop_service(self):
        status = self.service.get_service_status(self.service_name)
        if status == "NOT_FOUND":
            logger.error(f"Service {self.service_name} NOT FOUND.")
            self.stop_event.set()
            return
        logger.info(f"Current status: {status}")
        if status == "RUNNING":
            self.system.log_process_usage(self.service_process_name, self.log_dir)
            
            stopped = False
            if self.is_watchdog_mode:
                logger.info("Watchdog Mode: Stopping service...")
                self.service.stop_service(self.service_name, timeout=0)
                
                start_t = time.time()
                while time.time() - start_t < 30:
                    if self.stop_event.is_set(): return
                    pid_svc = self.system.get_process_pid(self.service_process_name)
                    pid_wd = self.system.get_process_pid(self.watchdog_process_name)
                    
                    if pid_svc == 0 and pid_wd == 0:
                        logger.info("Watchdog Mode: Services stopped successfully.")
                        stopped = True
                        break
                    time.sleep(1)
                
                if not stopped:
                    logger.warning("Watchdog Mode: Failed to stop in 30s. Waiting 60s...")
                    if smart_sleep(60, self.stop_event): return
                    
                    pid_svc = self.system.get_process_pid(self.service_process_name)
                    pid_wd = self.system.get_process_pid(self.watchdog_process_name)
                    
                    if pid_svc != 0:
                        logger.error(f"Watchdog Mode: Service stuck (PID {pid_svc}). Creating dump...")
                        self.diag.generate_live_dump(pid_svc, self.log_dir)

                    if pid_wd != 0:
                        logger.error(f"Watchdog Mode: Watchdog stuck (PID {pid_wd}). Creating dump...")
                        self.diag.generate_live_dump(pid_wd, self.log_dir)
                    
                    if pid_svc == 0 and pid_wd == 0:
                        stopped = True
            else:
                stopped = self.service.stop_service(self.service_name)

            if not stopped:
                logger.error(f"{self.service_name} failed to stop.")
                self.service.handle_non_stop(
                    self.service_name,
                    self.cfg_mgr.is_64bit,
                    self.log_dir
                )
                self.stop_event.set()
                return
            self.cur_svc_status = self.service.get_service_status(self.service_name)
            logger.info(f"Current status (Post-Stop): {self.cur_svc_status}")
            if smart_sleep(TINY_SEC, self.stop_event): return

    def exec_restart_driver(self):
        if self.service.get_service_status(self.drv_name) == "NOT_FOUND":
            logger.error(f"Driver {self.drv_name} NOT FOUND.")
            self.stop_event.set()
            return
        logger.info(f"To STOP and START driver 'stadrv'")
        self.service.stop_service(self.drv_name)
        status = self.service.get_service_status(self.service_name)
        logger.info(f"Current status: {status}")
        if smart_sleep(SHORT_SEC, self.stop_event): return
        self.service.start_service(self.drv_name)
        if smart_sleep(TINY_SEC, self.stop_event): return

    def exec_browser_tabs(self, urls):
        if not self.config.enable_browser_tabs_open:
            return []
        
        return util_traffic.open_browser_tabs(
            urls, self.tool_dir, self.config.browser_max_tabs,
            self.config.browser_max_memory, self.stop_event, self.log_dir, STD_SEC
        )

    def exec_curl_requests(self):
        util_traffic.curl_requests(self.urls, self.stop_event)

    def exec_validation_checks(self, process_map):
        if self.config.decouple_client:
            return True
        if not self.validation_enabled: return True
        if self.config.browser_log_validation != 0 or self.config.curl_flood_log_validation != 0:
            self.cfg_mgr.load_nsexception()
        if self.config.client_disabling_enabled and not self.client_enabled_event.is_set():
             logger.info("Validation skipped (Client is disabled).")
             return True
        return util_validate.validate_traffic_flow(
            process_map, self.stop_event, self.cfg_mgr.url_in_nsexception
        )

    def exec_on_off_prem(self, iteration):
        client_toggles = self.config.config_data.get("client_feature_toggling", {})
        onprem_cfg = client_toggles.get("webui_on_prem", {})
        if not onprem_cfg.get("enable", 0):
            return False

        target_host = onprem_cfg.get("onprem_http_host", "")
        if not target_host: return False

        if self.cfg_mgr.toggle_on_off_prem(target_host, iteration):
            return True
        return False

    def exec_tls_dtls_toggle(self, count):
        if not self.config.tls_dtls_toggle_enabled:
            return False
        if self.config.tls_dtls_toggle_interval <= 0:
            return False
        if count % self.config.tls_dtls_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False

        use_dtls = (self.current_protocol == "tls")
        success = self.webui_client.toggle_tls_dtls(use_dtls)
        if success:
            self.current_protocol = "dtls" if use_dtls else "tls"
            return True
        logger.warning("TLS/DTLS toggle failed.")
        return False

    def exec_steering_mode_toggle(self, count):
        if not self.config.steering_mode_toggle_enabled:
            return False
        if self.config.steering_mode_toggle_interval <= 0:
            return False
        if count % self.config.steering_mode_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False

        use_all = (self.current_steering_mode == "web")
        success = self.webui_client.toggle_steering_mode(use_all)
        if success:
            self.current_steering_mode = "all" if use_all else "web"
            return True
        logger.warning("Steering mode toggle failed.")
        return False

    def exec_webui_failclose_toggle(self, count):
        if not self.config.webui_failclose_toggle_enabled:
            return False
        if self.config.webui_failclose_toggle_interval <= 0:
            return False
        if count % self.config.webui_failclose_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False

        enable = not self.current_webui_failclose
        success = self.webui_client.toggle_webui_failclose(enable)
        if success:
            self.current_webui_failclose = enable
            return True
        logger.warning("WebUI failClose toggle failed.")
        return False

    def exec_sni_toggle(self, count):
        if not self.config.sni_toggle_enabled:
            return False
        if self.config.sni_toggle_interval <= 0:
            return False
        if count % self.config.sni_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False

        enable = not self.current_sni
        success = self.webui_client.toggle_sni_check(enable)
        if success:
            self.current_sni = enable
            return True
        logger.warning("SNI check toggle failed.")
        return False

    def exec_exception_domains_toggle(self, count):
        if not self.config.exception_domains_toggle_enabled:
            return False
        if self.config.exception_domains_toggle_interval <= 0:
            return False
        if count % self.config.exception_domains_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False
        if not self.config.exception_domains_list:
            return False

        add = not self.current_exception_domains_added
        success = self.webui_client.toggle_exception_domains(
            add, self.config.exception_domains_list
        )
        if success:
            self.current_exception_domains_added = add
            return True
        logger.warning("Exception domains toggle failed.")
        return False

    def exec_webui_client_disabling_toggle(self, count):
        if not self.config.webui_client_disabling_toggle_enabled:
            return False
        if self.config.webui_client_disabling_toggle_interval <= 0:
            return False
        if count % self.config.webui_client_disabling_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False

        enable = not self.current_webui_client_disabling
        success = self.webui_client.toggle_client_disabling(enable)
        if success:
            self.current_webui_client_disabling = enable
            return True
        logger.warning("WebUI client disabling toggle failed.")
        return False

    def exec_custom_ports_toggle(self, count):
        if not self.config.custom_ports_toggle_enabled:
            return False
        if self.config.custom_ports_toggle_interval <= 0:
            return False
        if count % self.config.custom_ports_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False
        if not self.config.custom_ports_list:
            return False

        add = not self.current_custom_ports_added
        success = self.webui_client.toggle_custom_ports(
            add, self.config.custom_ports_list
        )
        if success:
            self.current_custom_ports_added = add
            return True
        logger.warning("Custom ports toggle failed.")
        return False

    def exec_interop_proxy_toggle(self, count):
        if not self.config.interop_proxy_toggle_enabled:
            return False
        if self.config.interop_proxy_toggle_interval <= 0:
            return False
        if count % self.config.interop_proxy_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False

        enable = not self.current_interop_proxy
        success = self.webui_client.toggle_interop_proxy(
            enable,
            self.config.interop_proxy_host,
            self.config.interop_proxy_port
        )
        if success:
            self.current_interop_proxy = enable
            return True
        logger.warning("Interop proxy toggle failed.")
        return False

    def exec_mtu_toggle(self, count):
        if not self.config.mtu_toggle_enabled:
            return False
        if self.config.mtu_toggle_interval <= 0:
            return False
        if count % self.config.mtu_toggle_interval != 0:
            return False
        if not self.webui_client:
            return False

        mtu_val = self.config.mtu_values[
            self.mtu_index % len(self.config.mtu_values)
        ]
        success = self.webui_client.set_mtu(mtu_val)
        if success:
            self.mtu_index += 1
            return True
        logger.warning("MTU toggle failed.")
        return False

    def get_next_batch(self, batch_size):
        if not self.urls: return []
        if len(self.urls) <= batch_size:
            batch = self.urls[:]
            random.shuffle(self.urls)
            return batch
        end_idx = self.url_cursor + batch_size
        if end_idx <= len(self.urls):
            batch = self.urls[self.url_cursor : end_idx]
            self.url_cursor = end_idx
            if self.url_cursor == len(self.urls):
                 self.url_cursor = 0
                 random.shuffle(self.urls)
                 logger.info("All URLs used. Re-shuffling list.")
            return batch
        else:
            batch = self.urls[self.url_cursor :]
            random.shuffle(self.urls)
            logger.info("All URLs used. Re-shuffling list.")
            self.url_cursor = 0
            needed = batch_size - len(batch)
            if needed > 0:
                batch.extend(self.urls[0:needed])
                self.url_cursor = needed
            return batch

    def _run_decoupled(self):
        self.input.start_input_monitor(self.stop_event)
        self.header_msg()

        start_iter = 1
        if self.is_continue_mode and self.config.cur_iter > 0:
            start_iter = self.config.cur_iter + 1
            logger.info(
                f"Resuming from iteration {start_iter} "
                f"(Previous: {self.config.cur_iter})"
            )

        count = self.config.loop_times
        if start_iter > self.config.loop_times:
            logger.info(
                f"Already completed all {self.config.loop_times} iterations. "
                "Skipping run loop."
            )
            self.input.stop_input_monitor()
            logger.info(f"--------- Finished {count} iterations. ---------")
            return

        for count in range(start_iter, self.config.loop_times + 1):
            ITER_FILTER.iteration = count
            if self.stop_event.is_set():
                break

            try:
                pct = count / self.config.loop_times * 100
                msg = f" Iter {count}/{self.config.loop_times} ({pct:.1f}%) "
                logger.info(msg.center(60, "="))

                needed_size = 50
                if self.config.curl_flood_enabled:
                    needed_size += self.config.curl_flood_count
                if self.config.enable_browser_tabs_open:
                    needed_size += self.config.browser_max_tabs
                batch_size = max(50, needed_size)
                current_iter_urls = self.get_next_batch(batch_size)

                if self.config.dns_enabled:
                    dns_domains = [
                        urlparse(u).netloc or u.split('/')[0]
                        for u in current_iter_urls if u
                    ]
                    util_traffic.generate_dns_flood(
                        dns_domains,
                        self.config.dns_count,
                        self.config.dns_duration,
                        self.config.dns_concurrent,
                        self.stop_event,
                    )

                if self.config.curl_flood_enabled:
                    browser_count = (
                        self.config.browser_max_tabs
                        if self.config.enable_browser_tabs_open else 0
                    )
                    start_idx = (
                        browser_count
                        if len(current_iter_urls) >= (
                            self.config.curl_flood_count + browser_count
                        )
                        else 0
                    )
                    curl_targets = current_iter_urls[
                        start_idx:start_idx + self.config.curl_flood_count
                    ]
                    util_traffic.generate_curl_flood(
                        curl_targets,
                        self.config.curl_flood_count,
                        self.config.curl_flood_duration,
                        self.config.curl_flood_concurrent,
                        self.stop_event,
                    )

                if self.config.ftp_enabled:
                    util_traffic.generate_ftp_traffic(
                        self.config.ftp_target_ip,
                        self.config.ftp_target_port,
                        self.config.ftp_user,
                        self.config.ftp_password,
                        self.config.ftp_file_size_mb,
                        self.config.ftp_count,
                        self.config.ftp_duration,
                        self.config.ftp_concurrent,
                        self.stop_event,
                    )

                if self.config.ftps_enabled:
                    util_traffic.generate_ftps_traffic(
                        self.config.ftps_target_ip,
                        self.config.ftps_target_port,
                        self.config.ftps_user,
                        self.config.ftps_password,
                        self.config.ftps_file_size_mb,
                        self.config.ftps_count,
                        self.config.ftps_duration,
                        self.config.ftps_concurrent,
                        self.stop_event,
                    )

                if self.config.sftp_enabled:
                    util_traffic.generate_sftp_traffic(
                        self.config.sftp_target_ip,
                        self.config.sftp_target_port,
                        self.config.sftp_user,
                        self.config.sftp_password,
                        self.config.sftp_file_size_mb,
                        self.config.sftp_count,
                        self.config.sftp_duration,
                        self.config.sftp_concurrent,
                        self.stop_event,
                    )

                if self.config.udp_enabled:
                    use_ipv6 = bool(self.config.udp_target_ipv6)
                    target = (
                        self.config.udp_target_ipv6
                        if use_ipv6 else self.config.udp_target_ip
                    )
                    util_traffic.generate_udp_flood(
                        target,
                        self.config.udp_target_port,
                        self.config.udp_count,
                        self.config.udp_duration,
                        self.config.udp_concurrent,
                        self.stop_event,
                        use_ipv6,
                    )

                if (
                    (self.config.ab_duration > 0 or self.config.ab_total_conn > 0)
                    and self.config.ab_target_urls
                ):
                    for url in self.config.ab_target_urls:
                        if self.stop_event.is_set():
                            break
                        util_traffic.run_high_concurrency_test(
                            url,
                            self.config.ab_total_conn,
                            self.config.ab_concurrent,
                            self.tool_dir,
                            self.stop_event,
                            self.config.ab_duration,
                        )

                browser_targets = []
                if self.config.enable_browser_tabs_open:
                    needed = self.config.browser_max_tabs
                    browser_targets = current_iter_urls[:needed]
                self.exec_browser_tabs(browser_targets)

                if smart_sleep(2, self.stop_event):
                    break

                if self.config.enable_browser_tabs_open:
                    if sys.platform.startswith("win"):
                        ps_script = os.path.join(
                            self.tool_dir, "close_browsers.ps1"
                        )
                        self.system.run_shell_script(ps_script)
                    elif sys.platform.startswith("darwin"):
                        ps_script = os.path.join(
                            self.tool_dir, "close_browsers.sh"
                        )
                        self.system.run_shell_script(ps_script)
                    elif sys.platform.startswith("linux"):
                        ps_script = os.path.join(
                            self.tool_dir, "close_browsers.sh"
                        )
                        self.system.run_shell_script(ps_script)

                logger.info(f"Short sleep for {SHORT_SEC}s at iteration end.")
                if smart_sleep(SHORT_SEC, self.stop_event):
                    break

            except Exception:
                logger.exception("An error occurred:")
                if smart_sleep(STD_SEC, self.stop_event):
                    break

        logger.info(f"--------- Finished {count} iterations. ---------")

    def run(self):
        if self.config.decouple_client:
            self._run_decoupled()
            return

        self.input.start_input_monitor(self.stop_event)
        self.header_msg()
        self.start_client_thread()
        self.start_resource_monitor()

        start_iter = 1
        if self.is_continue_mode and self.config.cur_iter > 0:
            start_iter = self.config.cur_iter + 1
            logger.info(f"Resuming from iteration {start_iter} (Previous: {self.config.cur_iter})")

        count = self.config.loop_times
        if start_iter > self.config.loop_times:
            logger.info(f"Already completed all {self.config.loop_times} iterations. "
                       f"Skipping run loop.")
            self.input.stop_input_monitor()
            logger.info(f"--------- Finished {count} iterations. ---------")
            return

        for count in range(start_iter, self.config.loop_times + 1):
            ITER_FILTER.iteration = count
            if self.stop_event.is_set(): break
            try:
                pct = count / self.config.loop_times * 100
                msg = f" Iter {count}/{self.config.loop_times} ({pct:.1f}%) "
                logger.info(msg.center(60, "="))
                self.exec_start_service()
                if self.stop_event.is_set(): break

                if not self.cfg_mgr.is_local_cfg:
                    logger.info("Syncing client config via nsdiag...")
                    self.diag.sync_client_config(self.cfg_mgr.is_64bit)
                    logger.info("Client config sync finished.")
                else:
                    logger.info("Local config active, skip nsdiag update")

                if self.stop_event.is_set(): break

                needed_size = 50
                if self.config.curl_flood_enabled: needed_size += self.config.curl_flood_count
                if self.config.enable_browser_tabs_open: needed_size += self.config.browser_max_tabs
                batch_size = max(50, needed_size)
                current_iter_urls = self.get_next_batch(batch_size)
                
                curl_flood_urls = []
                if self.cfg_mgr.failclose_active:
                    logger.info("FailClose simulation active. Skipping traffic flooding.")
                else:
                    if self.config.dns_enabled:
                         dns_domains = [
                             urlparse(u).netloc or u.split('/')[0] for u in current_iter_urls if u
                         ]
                         util_traffic.generate_dns_flood(
                             dns_domains, self.config.dns_count, 
                             self.config.dns_duration, 
                             self.config.dns_concurrent, self.stop_event
                         )
                    
                    if self.config.curl_flood_enabled:
                        browser_count = (
                            self.config.browser_max_tabs if self.config.enable_browser_tabs_open else 0
                        )
                        start_idx = (
                            browser_count 
                            if len(current_iter_urls) >= (self.config.curl_flood_count + browser_count) 
                            else 0
                        )
                        curl_targets = current_iter_urls[start_idx : start_idx + self.config.curl_flood_count]
                        curl_flood_urls = util_traffic.generate_curl_flood(
                            curl_targets, self.config.curl_flood_count, self.config.curl_flood_duration, 
                            self.config.curl_flood_concurrent, self.stop_event
                        )

                    if self.config.ftp_enabled:
                        util_traffic.generate_ftp_traffic(
                            self.config.ftp_target_ip, self.config.ftp_target_port,
                            self.config.ftp_user, self.config.ftp_password,
                            self.config.ftp_file_size_mb, self.config.ftp_count,
                            self.config.ftp_duration, self.config.ftp_concurrent,
                            self.stop_event
                        )

                    if self.config.ftps_enabled:
                        util_traffic.generate_ftps_traffic(
                            self.config.ftps_target_ip, self.config.ftps_target_port,
                            self.config.ftps_user, self.config.ftps_password,
                            self.config.ftps_file_size_mb, self.config.ftps_count,
                            self.config.ftps_duration, self.config.ftps_concurrent,
                            self.stop_event
                        )

                    if self.config.sftp_enabled:
                        util_traffic.generate_sftp_traffic(
                            self.config.sftp_target_ip, self.config.sftp_target_port,
                            self.config.sftp_user, self.config.sftp_password,
                            self.config.sftp_file_size_mb, self.config.sftp_count,
                            self.config.sftp_duration, self.config.sftp_concurrent,
                            self.stop_event
                        )

                    if self.config.udp_enabled:
                        use_ipv6 = bool(self.config.udp_target_ipv6)
                        target = self.config.udp_target_ipv6 if use_ipv6 else self.config.udp_target_ip
                        util_traffic.generate_udp_flood(
                            target, self.config.udp_target_port,
                            self.config.udp_count, self.config.udp_duration,
                            self.config.udp_concurrent, self.stop_event, use_ipv6
                        )

                    # AB is enabled if either duration or total_conn > 0
                    if (self.config.ab_duration > 0 or self.config.ab_total_conn > 0) and self.config.ab_target_urls:
                        for url in self.config.ab_target_urls:
                            if self.stop_event.is_set(): break
                            util_traffic.run_high_concurrency_test(
                                url, self.config.ab_total_conn,
                                self.config.ab_concurrent, self.tool_dir,
                                self.stop_event, self.config.ab_duration
                            )

                if self.stop_event.is_set(): break

                if self.cfg_mgr.failclose_active:
                    self.exec_failclose_check()
                else:
                    browser_targets = []
                    if self.config.enable_browser_tabs_open:
                        needed = self.config.browser_max_tabs
                        browser_targets = current_iter_urls[:needed]
                    
                    browser_urls = self.exec_browser_tabs(browser_targets)
                    if smart_sleep(2, self.stop_event): break

                    validation_map = {}
                    check_browser = browser_urls and self.config.browser_log_validation
                    check_curl = curl_flood_urls and self.config.curl_flood_log_validation

                    if check_browser or check_curl:
                        logger.info("Waiting for logs to be flushed...")
                        smart_sleep(10, self.stop_event)

                    if check_browser: validation_map["msedge.exe"] = browser_urls
                    if check_curl:
                        if curl_flood_urls:
                             ratio = self.config.curl_flood_log_validation_ratio
                             sample_size = max(1, int(len(curl_flood_urls) * (ratio / 100.0)))
                             validation_map["curl.exe"] = random.sample(
                                 curl_flood_urls, min(len(curl_flood_urls), sample_size)
                             )

                    if not self.exec_validation_checks(validation_map):
                        logger.error("Validation failed! Stopping stress test.")
                        break
                
                # WebUI feature toggles (config sync, no service restart)
                webui_toggled = False
                if self.exec_tls_dtls_toggle(count):
                    webui_toggled = True
                if self.exec_steering_mode_toggle(count):
                    webui_toggled = True
                if self.exec_webui_failclose_toggle(count):
                    webui_toggled = True
                if self.exec_sni_toggle(count):
                    webui_toggled = True
                if self.exec_exception_domains_toggle(count):
                    webui_toggled = True
                if self.exec_webui_client_disabling_toggle(count):
                    webui_toggled = True
                if self.exec_custom_ports_toggle(count):
                    webui_toggled = True
                if self.exec_interop_proxy_toggle(count):
                    webui_toggled = True
                if self.exec_mtu_toggle(count):
                    webui_toggled = True
                if webui_toggled and not self.cfg_mgr.is_local_cfg:
                    self.diag.sync_client_config(self.cfg_mgr.is_64bit)

                # Check for Service Restart triggers
                restart_needed = False
                driver_restart_needed = False

                if self.exec_on_off_prem(count):
                    logger.info("On/Off Prem toggle triggered service restart.")
                    restart_needed = True

                if (
                    self.config.stop_svc_interval > 0 and
                    (count - self.last_svc_restart_count) >= self.config.stop_svc_interval
                ):
                     logger.info("Service stop interval triggered service restart.")
                     restart_needed = True

                if self.config.stop_drv_interval > 0 and count % self.config.stop_drv_interval == 0:
                    logger.info("Driver restart interval reached. Will restart driver.")
                    restart_needed = True
                    driver_restart_needed = True

                if (
                    self.config.failclose_enabled and 
                    self.config.failclose_interval > 0 and 
                    count % self.config.failclose_interval == 0
                ):
                    self.cfg_mgr.toggle_failclose()
                    logger.info("FailClose toggle triggered service restart.")
                    restart_needed = True

                if restart_needed:
                    self.exec_stop_service()
                    self.last_svc_restart_count = count
                    
                if driver_restart_needed:
                    self.exec_restart_driver()
                
                if self.stop_event.is_set(): break

                if self.config.long_idle_interval == 0:
                    sleep_dur = random.randint(30, 120)
                    logger.info(f"Random Sleep (idle=0). {sleep_dur}s...")
                    if smart_sleep(sleep_dur, self.stop_event): break

                s0_triggered = False
                if (
                    self.config.aoac_s0_standby_enabled and 
                    self.config.aoac_s0_standby_interval > 0 and 
                    count % self.config.aoac_s0_standby_interval == 0
                ):
                    logger.info(f"Perform AOAC S0. {self.config.aoac_s0_standby_duration}s")
                    self.power.enter_s0_and_wake(self.config.aoac_s0_standby_duration)
                    s0_triggered = True
                    if self.stop_event.is_set(): break

                s1_triggered = False
                if (
                    self.config.aoac_s1_standby_enabled and 
                    self.config.aoac_s1_standby_interval > 0 and 
                    count % self.config.aoac_s1_standby_interval == 0
                ):
                    if s0_triggered: logger.info("AOAC S1 skipped (S0 executed).")
                    else:
                        logger.info(f"Perform AOAC S1. {self.config.aoac_s1_standby_duration}s")
                        self.power.enter_s1_and_wake(self.config.aoac_s1_standby_duration)
                        s1_triggered = True
                        if self.stop_event.is_set(): break

                if (
                    self.config.aoac_s4_hibernate_enabled and 
                    self.config.aoac_s4_hibernate_interval > 0 and 
                    count % self.config.aoac_s4_hibernate_interval == 0
                ):
                    if s0_triggered or s1_triggered: logger.info("AOAC S4 skipped (S0/S1 executed).")
                    else:
                        if self.is_watchdog_mode:
                            pid = self.system.get_process_pid(self.service_process_name)
                            if pid != 0:
                                logger.info(
                                    "Watchdog Mode: Killing service process before S4 (PID %s)." % pid
                                )
                                try:
                                    subprocess.run(
                                        ["taskkill", "/PID", str(pid), "/F"],
                                        check=False
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Watchdog Mode: Failed to kill service (PID {pid}): {e}"
                                    )
                            else:
                                logger.info(
                                    "Watchdog Mode: Service process not running before S4."
                                )

                        logger.info(f"Perform AOAC S4. {self.config.aoac_s4_hibernate_duration}s")
                        self.power.enter_s4_and_wake(self.config.aoac_s4_hibernate_duration)
                        if self.is_watchdog_mode and not self.stop_event.is_set():
                            start_t = time.time()
                            revived = False
                            while time.time() - start_t < 90:
                                if self.stop_event.is_set():
                                    break
                                pid = self.system.get_process_pid(self.service_process_name)
                                if pid != 0:
                                    logger.info(
                                        f"Watchdog Mode: Service alive after S4 (PID {pid})."
                                    )
                                    revived = True
                                    break
                                time.sleep(1)
                            if not revived and not self.stop_event.is_set():
                                logger.warning(
                                    "Watchdog Mode: Service not running 90s after S4 wake."
                                )
                        if self.stop_event.is_set(): break

                if self.config.enable_browser_tabs_open:
                    if sys.platform.startswith("win"):
                        ps_script = os.path.join(self.tool_dir, "close_browsers.ps1")
                        self.system.run_shell_script(ps_script)
                    elif sys.platform.startswith("darwin"):
                        ps_script = os.path.join(self.tool_dir, "close_browsers.sh")
                        self.system.run_shell_script(ps_script)
                    elif sys.platform.startswith("linux"):
                        ps_script = os.path.join(self.tool_dir, "close_browsers.sh")
                        self.system.run_shell_script(ps_script)

                logger.info(f"Short sleep for {SHORT_SEC}s at iteration end.")
                if smart_sleep(SHORT_SEC, self.stop_event): break

                crash_found, zero_count = self.diag.check_crash_dumps(self.config.custom_dump_path)
                self.total_zero_dumps += zero_count
                if zero_count > 0: logger.info(f"Cleaned {zero_count} 0-byte dump files.")
                if crash_found:
                    logger.error("Crash dump found. Stopping test.")
                    self.diag.handle_crash(self.cfg_mgr.is_64bit, self.log_dir, self.config.custom_dump_path)
                    break

            except Exception:
                logger.exception("An error occurred:")
                if smart_sleep(STD_SEC, self.stop_event): break
            
            if self.config.reboot_interval > 0 and count % self.config.reboot_interval == 0:
                logger.info(f"Reboot interval ({self.config.reboot_interval}) reached.")
                self.config.cur_iter = count
                self.config.cur_log_dir = self.log_dir
                self.config.save()
                
                logger.info("Rebooting system...")
                self.reboot_pending = True
                self.power.reboot()
                break

        logger.info(f"--------- Finished {count} iterations. ---------")

if __name__ == "__main__":
    pass
