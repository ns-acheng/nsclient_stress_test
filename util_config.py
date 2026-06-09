import os
import sys
import shutil
import json
import logging
import fnmatch
from util_traffic import get_hostname_from_url
from interfaces.i_env import IEnvironment

logger = logging.getLogger()

class AgentConfigManager:
    def __init__(self, env: IEnvironment):
        self.dir_root = env.agent_data_dir
        self.stagent_root = self.dir_root
        
        self.target_nsconfig = os.path.join(self.stagent_root, "nsconfig.json")
        self.target_devconfig = os.path.join(self.stagent_root, "devconfig.json")
        self.backup_path = os.path.join("data", "nsconfig-bk.json")
        self.source_devconfig = os.path.join("data", "devconfig.json")
        self.hosts_bk = os.path.join("data", "hosts-bk")
        self.hosts_path = env.system_hosts_file

        self.is_64bit = False
        self.is_local_cfg = False
        self.is_false_close = False

        self.exception_path = os.path.join(
            self.stagent_root, "data", "nsexception.json"
        )
        self.exception_names = []
        self.gateway_hosts = []
        self.failclose_active = False
        self.last_setup_error = ""

    def check_watchdog_mode(self) -> bool:
        try:
            if not os.path.exists(self.target_nsconfig):
                return False
            
            with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            client_config = data.get("clientConfig", {})
            val = client_config.get("nsclient_watchdog_monitor")
            
            if val is True: return True
            if isinstance(val, str) and val.lower() == "true": return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking watchdog mode: {e}")
            return False

    def load_nsexception(self):
        self.exception_names = []
        if not os.path.exists(self.exception_path):
            logger.warning(f"nsexception.json not found at {self.exception_path}")
            return

        try:
            with open(self.exception_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, dict):
                if "names" in data and isinstance(data["names"], list):
                    self.exception_names.extend(data["names"])

            elif isinstance(data, list):
                for rule in data:
                    names = rule.get("names", [])
                    if isinstance(names, list):
                        self.exception_names.extend(names)

            logger.info(
                f"Loaded {len(self.exception_names)} exception patterns "
                f"from {self.exception_path}"
            )
        except Exception as e:
            logger.error(f"Failed to load nsexception.json: {e}")

    def url_in_nsexception(self, url: str) -> bool:
        try:
            host = get_hostname_from_url(url)
            if not host:
                return False

            host = host.lower()

            for pattern in self.exception_names:
                pattern = pattern.lower()

                if fnmatch.fnmatch(host, pattern):
                    return True

                if pattern.startswith("*.") and host == pattern[2:]:
                    return True

                if '*' not in pattern and host.endswith('.' + pattern):
                    return True

            return False
        except Exception:
            return False

    def get_tenant_hostname(self) -> str:
        try:
            if not os.path.exists(self.target_nsconfig):
                return ""

            with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                data = json.load(f)

            nsgw = data.get("nsgw", {})
            host = nsgw.get("host") 

            if not host:
                return ""

            parts = host.split('.')
            if parts and parts[0].startswith("gateway-"):
                parts[0] = parts[0].replace("gateway-", "")
                return ".".join(parts)

            return ""

        except Exception as e:
            logger.error(f"Error reading tenant hostname from nsconfig: {e}")
            return ""

    def setup_environment(self) -> bool:
        self.last_setup_error = ""
        check_path = r"C:\Program Files\Netskope\STAgent\stAgentSvc.exe"
        if os.path.exists(check_path):
            self.is_64bit = True
            logger.info(f"Detected 64-bit Agent: {check_path}")
        else:
            self.is_64bit = False
            logger.info("64-bit Agent path not found, assuming 32-bit.")

        if sys.platform == 'win32':
            try:
                from platforms.windows.service import WindowsServiceManager
                svc_mgr = WindowsServiceManager()
                if svc_mgr.get_service_status("stAgentSvc") == "NOT_FOUND":
                    self.last_setup_error = (
                        "Service 'stAgentSvc' not found. Client not installed."
                    )
                    logger.error(f"ABORT: {self.last_setup_error}")
                    return False
            except Exception as e:
                self.last_setup_error = f"Service check failed: {e}"
                logger.error(self.last_setup_error)
                return False
        
        if os.path.exists(self.target_nsconfig):
            try:
                with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                nsgw = data.get("nsgw", {})
                h1 = nsgw.get("host")
                h2 = nsgw.get("backupHost")

                if h1: self.gateway_hosts.append(h1)
                if h2: self.gateway_hosts.append(h2)

                logger.info(f"Loaded Gateway Hosts for FailClose simulation: {self.gateway_hosts}")

            except Exception as e:
                logger.error(f"Failed to load gateway hosts from nsconfig: {e}")
        else:
            logger.warning(f"nsconfig.json not found at {self.target_nsconfig}. Failclose will be disabled.")
            self.gateway_hosts = []


        if os.path.exists(self.hosts_path):
            try:
                shutil.copy(self.hosts_path, self.hosts_bk)
                logger.info(f"Backed up hosts file to {self.hosts_bk}")
            except Exception as e:
                logger.error(f"Failed to backup hosts file: {e}")
        
        return True

    def restore_config(self, remove_only=False):
        try:
            if os.path.exists(self.backup_path):
                if remove_only:
                    os.remove(self.backup_path)
                    logger.info(f"Removed backup {self.backup_path}")
                else:
                    shutil.move(self.backup_path, self.target_nsconfig)
                    logger.info(f"Restored {self.backup_path}")
            elif not remove_only:
                # Only log as info - backup may not exist if config wasn't modified
                logger.info(f"No backup to restore at {self.backup_path} (config was not modified).")

            if os.path.exists(self.target_devconfig):
                os.remove(self.target_devconfig)
                logger.info(f"Removed {self.target_devconfig}")

            if os.path.exists(self.hosts_bk):
                if remove_only:
                    os.remove(self.hosts_bk)
                else:
                    shutil.copy(self.hosts_bk, self.hosts_path)
                    logger.info(f"Restored hosts file from {self.hosts_bk}")

        except Exception as e:
            logger.error(f"Error during config restoration: {e}")
        self.is_local_cfg = False

    def modify_hosts_file_entries(self, entries: list, add_entries: bool):
        try:
            if not os.path.exists(self.hosts_path):
                return

            import stat
            if sys.platform.startswith("win"):
                os.chmod(self.hosts_path, stat.S_IWRITE)

            with open(self.hosts_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            new_lines = []
            
            # Create a set of "targets" to easily identify lines to remove/skip
            # targets = { "hostname": "ip" }
            targets = {}
            for ip, host in entries:
                targets[host.lower()] = ip

            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2:
                    current_host = parts[1].lower()

                    if current_host in targets:
                        # If we are adding, we might want to replace it (to ensure IP match) or skip duplication
                        # If we are removing, we skip it.
                        if add_entries:
                           pass # We will filter it out and re-add at the end to ensure freshness/correct IP
                        else:
                           continue # Skip (Remove)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            # Cleanup trailing newlines before appending
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] += '\n'

            if add_entries:
                for ip, host in entries:
                    logger.info(f"HostsFile: Adding {ip} {host}")
                    new_lines.append(f"{ip} {host}\n")
            else:
                 for ip, host in entries:
                    logger.info(f"HostsFile: Removing {host}")

            with open(self.hosts_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

        except Exception as e:
            logger.error(f"Failed to modify hosts file entries: {e}")

    def toggle_failclose(self):
        logger.info("Executing FailClose simulation (Hosts manipulation + Config update)...")
        try:
            if self.failclose_active:
                entries = [("10.1.1.1", h) for h in self.gateway_hosts]
                self.modify_hosts_file_entries(entries, add_entries=False)

                # Revert FailClose config to false
                if os.path.exists(self.target_nsconfig):
                     try:
                         with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                             ns_data = json.load(f)
                         
                         ns_data.setdefault("failClose", {})["fail_close"] = "false"
                         
                         with open(self.target_nsconfig, 'w', encoding='utf-8') as f:
                             json.dump(ns_data, f, indent=4)
                         logger.info("Updated nsconfig.json: fail_close = false")
                     except Exception as e:
                         logger.error(f"Failed to update nsconfig.json: {e}")

                self.failclose_active = False
                self.is_false_close = False
            else:
                if not self.gateway_hosts:
                    logger.warning("No gateway hosts loaded. Cannot simulate FailClose.")
                    return

                if not os.path.exists(self.hosts_bk) and os.path.exists(self.hosts_path):
                    shutil.copy(self.hosts_path, self.hosts_bk)
                
                if not os.path.exists(self.backup_path) and os.path.exists(self.target_nsconfig):
                    shutil.copy(self.target_nsconfig, self.backup_path)

                # Deploy devconfig for FailClose
                if os.path.exists(self.source_devconfig):
                    shutil.copy(self.source_devconfig, self.target_devconfig)
                    logger.info(f"Copied devconfig to {self.target_devconfig}")
                    self.is_local_cfg = True
                else:
                    logger.warning(
                        f"Source {self.source_devconfig} not found. "
                        "FailClose might not work as expected."
                    )

                if os.path.exists(self.target_nsconfig):
                     try:
                         with open(self.target_nsconfig, 'r', encoding='utf-8') as f:
                             ns_data = json.load(f)
                         ns_data.setdefault("failClose", {})["fail_close"] = "true"
                         with open(self.target_nsconfig, 'w', encoding='utf-8') as f:
                             json.dump(ns_data, f, indent=4)
                     except Exception as e:
                         logger.error(f"Failed to update nsconfig.json: {e}")

                entries = [("10.1.1.1", h) for h in self.gateway_hosts]
                self.modify_hosts_file_entries(entries, add_entries=True)
                
                self.failclose_active = True
                self.is_false_close = True
                    
        except Exception as e:
            logger.error(f"Error during FailClose simulation: {e}")

    def toggle_on_off_prem(self, target_host, iteration):
        # Current Iteration Logic:
        # Iter 1 (Odd) -> Currently On-Prem. End of iter: Prepare for Off-Prem (2).
        # Iter 2 (Even) -> Currently Off-Prem. End of iter: Prepare for On-Prem (3).
        
        is_odd = (iteration % 2 != 0)
        
        from urllib.parse import urlparse
        if "://" in target_host:
            hostname = urlparse(target_host).netloc
        else:
            hostname = target_host

        entries = [("10.1.1.1", hostname)]

        if is_odd:
            # Prepare for Even (Off-Prem)
            logger.info(f"End of Iter {iteration} (On-Prem). Switching to Off-Prem for next iter.")
            self.modify_hosts_file_entries(entries, add_entries=True)
        else:
            # Prepare for Odd (On-Prem)
            logger.info(f"End of Iter {iteration} (Off-Prem). Switching to On-Prem for next iter.")
            self.modify_hosts_file_entries(entries, add_entries=False)
        return True
