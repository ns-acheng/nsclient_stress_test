import json
import sys
import os
import logging

logger = logging.getLogger()

class ToolConfig:
    TRAFFIC_MAP = [
        {
            "json_key": "dns",
            "enable_attr": "dns_enabled",
            "fields": {
                "count": "dns_count",
                "duration_sec": "dns_duration",
                "concurrent_conn": "dns_concurrent"
            }
        },
        {
            "json_key": "udp",
            "enable_attr": "udp_enabled",
            "fields": {
                "count": "udp_count",
                "duration_sec": "udp_duration",
                "concurrent_conn": "udp_concurrent",
                "target_ip": "udp_target_ip",
                "target_ipv6": "udp_target_ipv6",
                "target_port": "udp_target_port"
            }
        },
        {
            "json_key": "https",
            "enable_attr": "curl_flood_enabled",
            "fields": {
                "count": "curl_flood_count",
                "duration_sec": "curl_flood_duration",
                "concurrent_conn": "curl_flood_concurrent",
                "log_validation": "curl_flood_log_validation",
                "log_validation_ratio": "curl_flood_log_validation_ratio"
            }
        },
        {
            "json_key": "ftp",
            "enable_attr": "ftp_enabled",
            "fields": {
                "count": "ftp_count",
                "duration_sec": "ftp_duration",
                "concurrent_conn": "ftp_concurrent",
                "target_ip": "ftp_target_ip",
                "target_port": "ftp_target_port",
                "user": "ftp_user",
                "password": "ftp_password",
                "file_size_mb": "ftp_file_size_mb"
            }
        },
        {
            "json_key": "ftps",
            "enable_attr": "ftps_enabled",
            "fields": {
                "count": "ftps_count",
                "duration_sec": "ftps_duration",
                "concurrent_conn": "ftps_concurrent",
                "target_ip": "ftps_target_ip",
                "target_port": "ftps_target_port",
                "user": "ftps_user",
                "password": "ftps_password",
                "file_size_mb": "ftps_file_size_mb"
            }
        },
        {
            "json_key": "sftp",
            "enable_attr": "sftp_enabled",
            "fields": {
                "count": "sftp_count",
                "duration_sec": "sftp_duration",
                "concurrent_conn": "sftp_concurrent",
                "target_ip": "sftp_target_ip",
                "target_port": "sftp_target_port",
                "user": "sftp_user",
                "password": "sftp_password",
                "file_size_mb": "sftp_file_size_mb"
            }
        }
    ]

    # Validation Rules: (Attribute, Min, Max, Default)
    RANGE_CONSTRAINTS = [
        ("client_enable_min", 180, 600, 180),
        ("client_enable_max", 600, 1200, 600),
        ("client_disable_ratio", 0.00001, 1.0, 0.15),
        ("browser_max_memory", 50, 99, 85),
        ("browser_max_tabs", 1, 300, 20),
        ("aoac_s0_standby_duration", 30, 120, 30),
        ("aoac_s1_standby_duration", 30, 120, 30),
        ("aoac_s4_hibernate_duration", 30, 120, 30),
        ("long_idle_time_min", 300, 7200, 300),
        ("long_idle_time_max", 300, 7200, 300),
        ("dns_count", 10, 10000, 50)
    ]

    # Traffic Validation: (Name, DurationAttr, CountAttr, ConcurrencyAttr, EnabledAttr)
    TRAFFIC_VALIDATION = [
        ("DNS", "dns_duration", "dns_count",
         "dns_concurrent", "dns_enabled"),
        ("UDP", "udp_duration", "udp_count",
         "udp_concurrent", "udp_enabled"),
        ("HTTPS", "curl_flood_duration", "curl_flood_count",
         "curl_flood_concurrent", "curl_flood_enabled"),
        ("AB", "ab_duration", "ab_total_conn", "ab_concurrent", None),
        ("FTP", "ftp_duration", "ftp_count", "ftp_concurrent", "ftp_enabled"),
        ("FTPS", "ftps_duration", "ftps_count", "ftps_concurrent", "ftps_enabled"),
        ("SFTP", "sftp_duration", "sftp_count", "sftp_concurrent", "sftp_enabled")
    ]

    def __init__(self, config_file: str):
        self.config_file = config_file
        self.state_file = r"data\state.json"

        self.loop_times = 1000
        self.stop_svc_interval = 1
        self.stop_drv_interval = 0
        self.reboot_interval = 0
        self.cur_iter = 0
        self.cur_log_dir = ""
        self.custom_dump_path = ""
        self.decouple_client = False

        self.failclose_enabled = True
        self.failclose_interval = 20

        self.tls_dtls_toggle_enabled = False
        self.tls_dtls_toggle_interval = 5
        self.steering_mode_toggle_enabled = False
        self.steering_mode_toggle_interval = 10
        self.webui_failclose_toggle_enabled = False
        self.webui_failclose_toggle_interval = 15
        self.sni_toggle_enabled = False
        self.sni_toggle_interval = 20
        self.exception_domains_toggle_enabled = False
        self.exception_domains_toggle_interval = 10
        self.exception_domains_list = []
        self.webui_client_disabling_toggle_enabled = False
        self.webui_client_disabling_toggle_interval = 10
        self.custom_ports_toggle_enabled = False
        self.custom_ports_toggle_interval = 10
        self.custom_ports_list = []
        self.interop_proxy_toggle_enabled = False
        self.interop_proxy_toggle_interval = 10
        self.interop_proxy_host = ""
        self.interop_proxy_port = 0
        self.mtu_toggle_enabled = False
        self.mtu_toggle_interval = 10
        self.mtu_values = [1400, 1200, 800, ""]

        self.client_disabling_enabled = False
        self.client_enable_min = 180
        self.client_enable_max = 600
        self.client_disable_ratio = 0.15

        self.aoac_s0_standby_enabled = False
        self.aoac_s0_standby_interval = 0
        self.aoac_s0_standby_duration = 10

        self.aoac_s1_standby_enabled = False
        self.aoac_s1_standby_interval = 0
        self.aoac_s1_standby_duration = 10

        self.aoac_s4_hibernate_enabled = False
        self.aoac_s4_hibernate_interval = 0
        self.aoac_s4_hibernate_duration = 10

        self.long_idle_interval = 0
        self.long_idle_time_min = 300
        self.long_idle_time_max = 300

        self.enable_browser_tabs_open = 1
        self.browser_max_memory = 85
        self.browser_max_tabs = 20
        self.browser_log_validation = 0

        self.dns_enabled = False
        self.dns_count = 50
        self.dns_duration = 0
        self.dns_concurrent = 20

        self.udp_enabled = False
        self.udp_target_ip = "127.0.0.1"
        self.udp_target_ipv6 = ""
        self.udp_target_port = 8080
        self.udp_duration = 10
        self.udp_count = 0
        self.udp_concurrent = 1

        self.ab_total_conn = 10000
        self.ab_concurrent = 0
        self.ab_duration = 0
        self.ab_target_urls = ["https://google.com"]

        self.curl_flood_enabled = False
        self.curl_flood_count = 1000
        self.curl_flood_duration = 0
        self.curl_flood_concurrent = 50
        self.curl_flood_log_validation = 0
        self.curl_flood_log_validation_ratio = 5

        self.ftp_enabled = False
        self.ftp_target_ip = "127.0.0.1"
        self.ftp_target_port = 21
        self.ftp_user = "test"
        self.ftp_password = "password"
        self.ftp_file_size_mb = 10
        self.ftp_duration = 10
        self.ftp_count = 0
        self.ftp_concurrent = 1

        self.ftps_enabled = False
        self.ftps_target_ip = "127.0.0.1"
        self.ftps_target_port = 990
        self.ftps_user = "test"
        self.ftps_password = "password"
        self.ftps_file_size_mb = 10
        self.ftps_duration = 10
        self.ftps_count = 0
        self.ftps_concurrent = 1

        self.sftp_enabled = False
        self.sftp_target_ip = "127.0.0.1"
        self.sftp_target_port = 2222
        self.sftp_user = "test"
        self.sftp_password = "password"
        self.sftp_file_size_mb = 10
        self.sftp_duration = 10
        self.sftp_count = 0
        self.sftp_concurrent = 1

    def load(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Strip // style comments (string-aware approach)
            lines = []
            for line in content.split('\n'):
                # Remove // comments only when outside of quoted strings
                cleaned = []
                in_string = False
                escape_next = False
                i = 0

                while i < len(line):
                    char = line[i]

                    # Handle escape sequences
                    if escape_next:
                        cleaned.append(char)
                        escape_next = False
                        i += 1
                        continue

                    # Check for escape character
                    if char == '\\' and in_string:
                        cleaned.append(char)
                        escape_next = True
                        i += 1
                        continue

                    # Toggle string state on unescaped quotes
                    if char == '"':
                        in_string = not in_string
                        cleaned.append(char)
                        i += 1
                        continue

                    # Check for // comment outside of strings
                    if not in_string and char == '/' and i + 1 < len(line) and line[i + 1] == '/':
                        # Found a comment, stop processing this line
                        break

                    cleaned.append(char)
                    i += 1

                line_cleaned = ''.join(cleaned).rstrip()
                # Skip empty lines that result from full-line comments
                if line_cleaned or not line.strip().startswith('//'):
                    lines.append(line_cleaned)

            cleaned_content = '\n'.join(lines)
            config = json.loads(cleaned_content)
            self.config_data = config
            logger.info(f"Loaded configuration from {self.config_file}")

            self.loop_times = config.get('loop_times', self.loop_times)
            self.stop_svc_interval = config.get('stop_svc_interval', self.stop_svc_interval)
            self.stop_drv_interval = config.get('stop_drv_interval', self.stop_drv_interval)
            self.reboot_interval = config.get('reboot_interval', self.reboot_interval)
            self.custom_dump_path = config.get('custom_dump_path', self.custom_dump_path)
            self.decouple_client = bool(config.get('decouple_client', self.decouple_client))

            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        state_data = json.load(f)
                    self.cur_iter = state_data.get('cur_iter', 0)
                    self.cur_log_dir = state_data.get('cur_log_dir', "")
                    logger.info(f"Loaded state from {self.state_file}")
                except Exception as e:
                    logger.warning(f"Failed to load state: {e}")
            self.long_idle_interval = config.get('long_idle_interval', self.long_idle_interval)
            self.long_idle_time_min = config.get('long_idle_time_min', self.long_idle_time_min)
            self.long_idle_time_max = config.get('long_idle_time_max', self.long_idle_time_max)

            cft = config.get('client_feature_toggling', {})
            power_cfg = config.get('power_test', {})

            fc = cft.get('failclose', {})
            self.failclose_enabled = bool(fc.get('enable', self.failclose_enabled))
            self.failclose_interval = fc.get('interval', self.failclose_interval)

            tls_dtls = cft.get('webui_tls_dtls_toggle', {})
            self.tls_dtls_toggle_enabled = bool(
                tls_dtls.get('enable', self.tls_dtls_toggle_enabled)
            )
            self.tls_dtls_toggle_interval = tls_dtls.get(
                'interval', self.tls_dtls_toggle_interval
            )

            steer = cft.get('webui_steering_mode_toggle', {})
            self.steering_mode_toggle_enabled = bool(
                steer.get('enable', self.steering_mode_toggle_enabled)
            )
            self.steering_mode_toggle_interval = steer.get(
                'interval', self.steering_mode_toggle_interval
            )

            wfc = cft.get('webui_failclose_toggle', {})
            self.webui_failclose_toggle_enabled = bool(
                wfc.get('enable', self.webui_failclose_toggle_enabled)
            )
            self.webui_failclose_toggle_interval = wfc.get(
                'interval', self.webui_failclose_toggle_interval
            )

            sni = cft.get('webui_sni_toggle', {})
            self.sni_toggle_enabled = bool(
                sni.get('enable', self.sni_toggle_enabled)
            )
            self.sni_toggle_interval = sni.get(
                'interval', self.sni_toggle_interval
            )

            exc_dom = cft.get('webui_exception_domains_toggle', {})
            self.exception_domains_toggle_enabled = bool(
                exc_dom.get('enable', self.exception_domains_toggle_enabled)
            )
            self.exception_domains_toggle_interval = exc_dom.get(
                'interval', self.exception_domains_toggle_interval
            )
            self.exception_domains_list = exc_dom.get(
                'exception_domains', self.exception_domains_list
            )
            if not isinstance(self.exception_domains_list, list):
                self.exception_domains_list = []

            wcd = cft.get('webui_client_disabling_toggle', {})
            self.webui_client_disabling_toggle_enabled = bool(
                wcd.get('enable', self.webui_client_disabling_toggle_enabled)
            )
            self.webui_client_disabling_toggle_interval = wcd.get(
                'interval', self.webui_client_disabling_toggle_interval
            )

            cp = cft.get('webui_custom_ports_toggle', {})
            self.custom_ports_toggle_enabled = bool(
                cp.get('enable', self.custom_ports_toggle_enabled)
            )
            self.custom_ports_toggle_interval = cp.get(
                'interval', self.custom_ports_toggle_interval
            )
            self.custom_ports_list = cp.get(
                'custom_ports', self.custom_ports_list
            )
            if not isinstance(self.custom_ports_list, list):
                self.custom_ports_list = []

            ip = cft.get('webui_interop_proxy_toggle', {})
            self.interop_proxy_toggle_enabled = bool(
                ip.get('enable', self.interop_proxy_toggle_enabled)
            )
            self.interop_proxy_toggle_interval = ip.get(
                'interval', self.interop_proxy_toggle_interval
            )
            self.interop_proxy_host = ip.get(
                'host', self.interop_proxy_host
            )
            self.interop_proxy_port = ip.get(
                'port', self.interop_proxy_port
            )

            mtu = cft.get('webui_mtu_toggle', {})
            self.mtu_toggle_enabled = bool(
                mtu.get('enable', self.mtu_toggle_enabled)
            )
            self.mtu_toggle_interval = mtu.get(
                'interval', self.mtu_toggle_interval
            )
            mtu_vals = mtu.get('mtu_values', self.mtu_values)
            if isinstance(mtu_vals, list) and len(mtu_vals) >= 2:
                self.mtu_values = mtu_vals
            else:
                self.mtu_values = [1400, 1200, 800, ""]

            cd = cft.get('client_disabling', {})
            self.client_disabling_enabled = bool(cd.get('enable', self.client_disabling_enabled))
            self.client_enable_min = cd.get('enable_sec_min', self.client_enable_min)
            self.client_enable_max = cd.get('enable_sec_max', self.client_enable_max)
            self.client_disable_ratio = cd.get('disable_ratio', self.client_disable_ratio)

            aoac = power_cfg.get('aoac_s0_standby', cft.get('aoac_s0_standby', {}))
            self.aoac_s0_standby_enabled = bool(aoac.get('enable', self.aoac_s0_standby_enabled))
            self.aoac_s0_standby_interval = aoac.get('interval', self.aoac_s0_standby_interval)
            self.aoac_s0_standby_duration = aoac.get('duration_sec', self.aoac_s0_standby_duration)

            aoac_s1 = power_cfg.get('aoac_s1_standby', cft.get('aoac_s1_standby', {}))
            self.aoac_s1_standby_enabled = bool(aoac_s1.get('enable', self.aoac_s1_standby_enabled))
            self.aoac_s1_standby_interval = aoac_s1.get('interval', self.aoac_s1_standby_interval)
            self.aoac_s1_standby_duration = aoac_s1.get('duration_sec', self.aoac_s1_standby_duration)

            aoac_s4 = power_cfg.get('aoac_s4_hibernate', cft.get('aoac_s4_hibernate', {}))
            self.aoac_s4_hibernate_enabled = bool(
                aoac_s4.get('enable', self.aoac_s4_hibernate_enabled)
            )
            self.aoac_s4_hibernate_interval = aoac_s4.get(
                'interval', self.aoac_s4_hibernate_interval
            )
            self.aoac_s4_hibernate_duration = aoac_s4.get(
                'duration_sec', self.aoac_s4_hibernate_duration
            )

            tg = config.get('traffic_gen', {})
            browser = tg.get('browser', {})
            self.enable_browser_tabs_open = browser.get('enable', self.enable_browser_tabs_open)
            self.browser_log_validation = browser.get('log_validation', self.browser_log_validation)
            self.browser_max_memory = browser.get('max_memory', self.browser_max_memory)
            self.browser_max_tabs = browser.get('max_tabs', self.browser_max_tabs)

            for proto in self.TRAFFIC_MAP:
                section = tg.get(proto['json_key'], {})
                current_enabled = getattr(self, proto['enable_attr'])
                setattr(self, proto['enable_attr'], bool(section.get('enable', current_enabled)))

                for json_field, attr_name in proto['fields'].items():
                    current_val = getattr(self, attr_name)
                    setattr(self, attr_name, section.get(json_field, current_val))

            ab = tg.get('ab', {})
            ab_enabled = ab.get('enable', 1)
            self.ab_concurrent = ab.get('concurrent_conn', self.ab_concurrent)
            self.ab_duration = ab.get('duration_sec', self.ab_duration)
            self.ab_total_conn = ab.get('total_conn', self.ab_total_conn)

            if not ab_enabled:
                self.ab_total_conn = 0
                self.ab_duration = 0

            self.ab_target_urls = ab.get('target_urls', self.ab_target_urls)
            if not isinstance(self.ab_target_urls, list):
                if self.ab_target_urls:
                    self.ab_target_urls = [self.ab_target_urls]
                else:
                    self.ab_target_urls = ["https://google.com"]

        except Exception as e:
            logger.error(f"Error loading config: {e}. Exiting.")
            sys.exit(1)

        self._validate()

    def save(self):
        try:
            py_path = os.path.join(sys.base_prefix, "python.exe")

            state_data = {
                "cur_iter": self.cur_iter,
                "cur_log_dir": self.cur_log_dir,
                "python_path": py_path
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _validate(self):
        if not isinstance(self.loop_times, int) or self.loop_times <= 0:
            logger.error(f"invalid 'loop_times'. Exiting.")
            sys.exit(1)
        if self.stop_svc_interval < 0:
            logger.error(f"invalid 'stop_svc_interval'. Exiting.")
            sys.exit(1)
        if self.reboot_interval < 0:
            logger.error(f"invalid 'reboot_interval'. Exiting.")
            sys.exit(1)
        if self.failclose_interval < 0:
            logger.error(f"invalid 'failclose_interval'. Exiting.")
            sys.exit(1)
        if self.tls_dtls_toggle_interval < 0:
            logger.error("invalid 'tls_dtls_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.steering_mode_toggle_interval < 0:
            logger.error("invalid 'steering_mode_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.webui_failclose_toggle_interval < 0:
            logger.error("invalid 'webui_failclose_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.sni_toggle_interval < 0:
            logger.error("invalid 'sni_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.exception_domains_toggle_interval < 0:
            logger.error("invalid 'exception_domains_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.webui_client_disabling_toggle_interval < 0:
            logger.error("invalid 'webui_client_disabling_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.custom_ports_toggle_interval < 0:
            logger.error("invalid 'custom_ports_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.interop_proxy_toggle_interval < 0:
            logger.error("invalid 'interop_proxy_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.mtu_toggle_interval < 0:
            logger.error("invalid 'mtu_toggle_interval'. Exiting.")
            sys.exit(1)
        if self.stop_drv_interval < 0:
            logger.error(f"invalid 'stop_drv_interval'. Exiting.")
            sys.exit(1)
        if self.aoac_s0_standby_interval < 0:
            logger.error("invalid 'aoac_s0_standby_interval'. Exiting.")
            sys.exit(1)
        if self.aoac_s1_standby_interval < 0:
            logger.error("invalid 'aoac_s1_standby_interval'. Exiting.")
            sys.exit(1)
        if self.aoac_s4_hibernate_interval < 0:
            logger.error("invalid 'aoac_s4_hibernate_interval'. Exiting.")
            sys.exit(1)

        for attr, min_val, max_val, default in self.RANGE_CONSTRAINTS:
            val = getattr(self, attr)
            if not (min_val <= val <= max_val):
                logger.warning(f"Invalid '{attr}' ({val}). Reset to {default}.")
                setattr(self, attr, default)

        if self.client_enable_max < self.client_enable_min:
            logger.warning("client_enable_max < min, adjusting to min.")
            self.client_enable_max = self.client_enable_min

        if self.long_idle_time_max < self.long_idle_time_min:
            logger.warning("long_idle_time_max < min, adjusting to min.")
            self.long_idle_time_max = self.long_idle_time_min

        for name, dur_attr, count_attr, conc_attr, enabled_attr in self.TRAFFIC_VALIDATION:
            if enabled_attr and not getattr(self, enabled_attr):
                continue

            dur = getattr(self, dur_attr)
            count = getattr(self, count_attr)
            conc = getattr(self, conc_attr)

            new_dur, new_count = self._cap_duration_count(dur, count, name)
            setattr(self, dur_attr, new_dur)
            setattr(self, count_attr, new_count)

            new_conc = self._cap_concurrency(conc, name)
            setattr(self, conc_attr, new_conc)

            if enabled_attr:
                is_valid = self._validate_traffic_section(True, new_dur, new_count, name)
                setattr(self, enabled_attr, is_valid)
            else:
                if new_dur <= 0 and new_count <= 0:
                     pass

        if self.ab_total_conn == 0 and self.ab_duration == 0:
             pass

        if self.ab_duration > 0 and self.ab_total_conn <= 0:
             self.ab_total_conn = 1

    def _validate_traffic_section(self, enabled, duration, count, name):
        if not enabled:
            return False
        if duration <= 0 and count <= 0:
            logger.warning(f"Both duration and count are 0 for {name}. Disabling.")
            return False
        return True

    def _cap_duration_count(self, duration, count, name):
        new_duration = duration
        new_count = count
        # Cap at 6 hours (21600 seconds)
        if new_duration > 21600:
            logger.warning(f"{name} duration {new_duration} > 21600. Capping at 21600.")
            new_duration = 21600
        if new_count > 2000000000:
            logger.warning(f"{name} count {new_count} > 2000000000. Capping at 2000000000.")
            new_count = 2000000000
        return new_duration, new_count

    def _cap_concurrency(self, concurrency, name):
        new_concurrency = concurrency

        if name in ["FTP", "FTPS", "SFTP"]:
            if new_concurrency < 1:
                logger.warning(f"{name} concurrency {new_concurrency} < 1. Resetting to 1.")
                new_concurrency = 1
            if new_concurrency > 50:
                logger.warning(f"{name} concurrency {new_concurrency} > 50. Capping at 50.")
                new_concurrency = 50
            return new_concurrency

        if new_concurrency < 10:
            logger.warning(f"{name} concurrency {new_concurrency} < 10. Resetting to 10.")
            new_concurrency = 10
        if new_concurrency > 1024:
            logger.warning(f"{name} concurrency {new_concurrency} > 1024. Capping at 1024.")
            new_concurrency = 1024
        return new_concurrency
