import sys
import os
import json
import logging

# Add sibling repo 'pylark-webapi-lib/src' to sys.path
#   parent/
#     stress_test/ (current repo)
#     pylark-webapi-lib/ (sibling repo)
#       src/
#         webapi/
current_dir = os.path.dirname(os.path.abspath(__file__))
sibling_repo_path = os.path.abspath(
    os.path.join(current_dir, "..", "pylark-webapi-lib", "src")
)

if os.path.exists(sibling_repo_path):
    if sibling_repo_path not in sys.path:
        sys.path.append(sibling_repo_path)
else:
    # Fallback: Try looking for a 'lib' folder inside stress_test (for portable deployments)
    local_lib_path = os.path.join(current_dir, "lib", "pylark-webapi-lib", "src")
    if os.path.exists(local_lib_path):
        if local_lib_path not in sys.path:
            sys.path.append(local_lib_path)

try:
    from webapi import WebAPI
    from webapi.auth import Authentication
    from webapi.settings.security_cloud_platform.netskope_client.client_configuration import (
        ClientConfiguration
    )
    from webapi.settings.security_cloud_platform.traffic_steering.steering_configuration import (
        SteeringConfiguration
    )
except ImportError:
    logging.getLogger(__name__).warning(
        "Failed to import pylark-webapi-lib. WebUI features will be unavailable."
    )
    WebAPI = None

logger = logging.getLogger(__name__)

class WebUIClient:
    DEFAULT_CONFIG = "Default tenant config"

    def __init__(self, hostname, username, password):
        if not WebAPI:
            raise ImportError("pylark-webapi-lib not found")

        self.hostname = hostname
        self.username = username
        self.password = password
        self.webapi = None
        self.is_logged_in = False
        self.client_config_name = self.DEFAULT_CONFIG
        self.steering_config_name = self.DEFAULT_CONFIG

    def login(self):
        try:
            logger.info(f"Connecting to WebUI {self.hostname} as {self.username}")
            self.webapi = WebAPI(
                hostname=self.hostname,
                username=self.username,
                password=self.password
            )
            auth = Authentication(self.webapi)
            import io
            import contextlib
            stderr_capture = io.StringIO()
            with contextlib.redirect_stderr(stderr_capture):
                auth.login()
            captured = stderr_capture.getvalue()
            if "webui_v2_apis" in captured or "cpcs" in captured:
                logger.warning(
                    "CPCS auth module not available (webui_v2_apis). "
                    "Using legacy login. Tests can continue."
                )
            elif captured.strip():
                sys.stderr.write(captured)
            self.is_logged_in = True
            logger.info("WebUI Login successful")
            return True
        except Exception as e:
            logger.error(f"WebUI Login failed: {e}")
            self.is_logged_in = False
            return False

    def load_config_names_from_local(self, stagent_root: str):
        """Read config names from local nsconfig.json and nssteering.json."""
        try:
            nsconfig_path = os.path.join(stagent_root, "nsconfig.json")
            if os.path.exists(nsconfig_path):
                with open(nsconfig_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                name = data.get("clientConfig", {}).get("configurationName", "")
                if name:
                    self.client_config_name = name

            nssteering_path = os.path.join(stagent_root, "data", "nssteering.json")
            if os.path.exists(nssteering_path):
                with open(nssteering_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                name = data.get("steering_config_name", "")
                if name:
                    self.steering_config_name = name

            logger.info(
                f"Config names - Client: '{self.client_config_name}', "
                f"Steering: '{self.steering_config_name}'"
            )
        except Exception as e:
            logger.warning(f"Failed to read local config names, using defaults: {e}")

    def update_client_config(self, config_name="Default tenant config", **kwargs):
        """
        Updates Client Configuration.
        Example kwargs: onpremcheck=1, onprem_use_dns=0, onprem_http_host="http://googleapi.com"
        """
        if not self.is_logged_in:
            if not self.login():
                return False

        try:
            client_config = ClientConfiguration(self.webapi)
            logger.info(f"Updating client configuration '{config_name}' with {kwargs}")

            if 'search_config' not in kwargs:
                kwargs['search_config'] = config_name

            response = client_config.update_client_config(**kwargs)
            
            if response.get('status') == 'success':
                logger.info("Client Config Update successful!")
                return True
            else:
                logger.error(f"Client Config Update failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"An error occurred during Client Config update: {e}")
            return False
                              

    def update_steering_config(
        self, config_name="Default tenant config", traffic_mode=None, exception_domains=None
    ):
        """
        Updates Steering Configuration.
        traffic_mode: "web", "all", etc.
        exception_domains: list of strings ["example.com"]
        """
        if not self.is_logged_in:
            if not self.login():
                return False

        try:
            steering_config = SteeringConfiguration(self.webapi)
            
            if traffic_mode:
                logger.info(
                    f"Updating traffic steering mode to '{traffic_mode}' for '{config_name}'"
                )
                steering_config.update_traffic_steering_mode(
                    traffic_mode=traffic_mode,
                    config_name=config_name
                )

            if exception_domains:
                logger.info(f"Adding exception domains to '{config_name}': {exception_domains}")
                steering_config.add_exception_domains(
                    domain_list=exception_domains,
                    config_name=config_name
                )
            
            return True

        except Exception as e:
            logger.error(f"An error occurred during Steering Config update: {e}")
            return False

    def toggle_tls_dtls(self, use_dtls: bool) -> bool:
        """Toggle tunnel protocol between TLS and DTLS."""
        protocol = "dtls" if use_dtls else "tls"
        enable_dtls = 1 if use_dtls else 0
        logger.info(f"Toggling tunnel protocol to {protocol} (enableDTLS={enable_dtls})")
        return self.update_client_config(
            self.client_config_name, protocol=protocol, enableDTLS=enable_dtls
        )

    def toggle_steering_mode(self, use_all: bool) -> bool:
        """Toggle steering mode between 'all' and 'web'."""
        mode = "all" if use_all else "web"
        logger.info(f"Toggling steering mode to {mode}")
        return self.update_steering_config(
            config_name=self.steering_config_name, traffic_mode=mode
        )

    def toggle_webui_failclose(self, enable: bool) -> bool:
        """Toggle failClose via WebUI API."""
        val = 1 if enable else 0
        logger.info(f"Toggling WebUI failClose to {val}")
        return self.update_client_config(self.client_config_name, failClose=val)

    def toggle_sni_check(self, enable: bool) -> bool:
        """Toggle SNI checking via WebUI API."""
        val = "true" if enable else "false"
        logger.info(f"Toggling SNI check to {val}")
        return self.update_client_config(self.client_config_name, checkSNI=val)

    def toggle_exception_domains(self, add: bool, domains: list) -> bool:
        """Add or remove exception domains from steering config."""
        if not domains:
            logger.warning("No exception domains provided.")
            return False
        if not self.is_logged_in:
            if not self.login():
                return False
        try:
            steering_config = SteeringConfiguration(self.webapi)
            if add:
                logger.info(f"Adding exception domains: {domains}")
                steering_config.add_exception_domains(
                    domain_list=domains,
                    config_name=self.steering_config_name
                )
            else:
                logger.info(f"Removing exception domains: {domains}")
                steering_config.remove_exception_domains(
                    domain_list=domains,
                    config_name=self.steering_config_name
                )
            return True
        except Exception as e:
            logger.error(f"Exception domains toggle failed: {e}")
            return False

    def toggle_client_disabling(self, enable: bool) -> bool:
        """Toggle allowClientDisabling via WebUI API."""
        val = 1 if enable else 0
        logger.info(f"Toggling allowClientDisabling to {val}")
        return self.update_client_config(
            self.client_config_name, allowClientDisabling=val
        )

    def toggle_custom_ports(self, add: bool, ports: list) -> bool:
        """Add or remove custom steered ports from steering config."""
        if not ports:
            logger.warning("No custom ports provided.")
            return False
        if not self.is_logged_in:
            if not self.login():
                return False
        try:
            steering_config = SteeringConfiguration(self.webapi)
            if add:
                logger.info(f"Adding custom ports: {ports}")
                steering_config.add_custom_ports(
                    ports=ports,
                    config_name=self.steering_config_name
                )
            else:
                logger.info(f"Removing custom ports: {ports}")
                steering_config.delete_custom_ports(
                    ports=ports,
                    config_name=self.steering_config_name
                )
            return True
        except Exception as e:
            logger.error(f"Custom ports toggle failed: {e}")
            return False

    def toggle_interop_proxy(self, enable: bool, host: str = "",
                             port: int = 0) -> bool:
        """Toggle interopProxy via WebUI API."""
        val = 1 if enable else 0
        logger.info(
            f"Toggling interopProxy to {val} (host={host}, port={port})"
        )
        kwargs = {"interopProxy": val}
        if enable and host:
            kwargs["interopProxy_host"] = host
            kwargs["interopProxy_port"] = port
        return self.update_client_config(self.client_config_name, **kwargs)

    def set_mtu(self, mtu_value) -> bool:
        """Set MTU value via WebUI API."""
        logger.info(f"Setting MTU to {mtu_value}")
        return self.update_client_config(
            self.client_config_name, mtu=mtu_value
        )

def perform_onprem_setup(config, hostname, password):
    client_toggles = config.get("client_feature_toggling", {})
    onprem_cfg = client_toggles.get("webui_on_prem", {})

    if not onprem_cfg.get("enable", 0):
        logger.warning("On-prem setup is not enabled. Skipping WebUI setup.")
        return False

    webui_cfg = client_toggles.get("webui_login", {})
    
    # If tenant_hostname is in config, use it. Otherwise keep the passed hostname.
    cfg_hostname = webui_cfg.get("tenant_hostname", "")
    if cfg_hostname:
        hostname = cfg_hostname

    username = webui_cfg.get("tenant_username", "")

    if not hostname or not username:
        logger.error("WebUI feature enabled but tenant_hostname or tenant_username is missing configuration.")
        return False

    client = WebUIClient(hostname, username, password)
    if client.login():
        use_dns = onprem_cfg.get("onprem_use_dns", 0)
        http_host = onprem_cfg.get("onprem_http_host", "")
        
        client.update_client_config(
            onpremcheck=1,
            onprem_use_dns=int(use_dns),
            onprem_http_host=http_host
        )
        return True
    logger.warning("WebUI setup failed due to login failure.")
    return False

if __name__ == "__main__":
    hostname = 'ac-stg01.stg.boomskope.com'
    username = 'acheng@netskope.com'
    password = input("Enter password: ")

    client = WebUIClient(hostname, username, password)
    if client.login():
        print("Login successful.")
        client.update_client_config(
            onpremcheck=1,
            onprem_use_dns=0,
            onprem_http_host="http://googleapi.com"
        )
        client.update_steering_config(
            traffic_mode="all"
        )
    else:
        print("Login failed.")
