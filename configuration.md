# Configuration (config.json)

* Before running the tool, review and edit `data/config.json` based on the test scenario you want to run.
* In default, it triggers HTTPS flooding for 10 iterations.
* To enable or disable any feature, simply modify the value(s) to `1`: 
```
 "enable": 0
```

## Config.json

`loop_times`: Total number of test iterations.

`stop_svc_interval`: Iteration frequency to stop/start the main service. Set to 0 to disable.

`stop_drv_interval`: Iteration frequency to restart the driver (nested within service stop). Set to 0 to disable.

`reboot_interval`: Iteration frequency to reboot the machine. The tool will automatically create a scheduled task to resume execution after login. Set to 0 to disable.

### Client Feature Toggling (client_feature_toggling)

This section controls client state toggles (non-power). Each feature has an `enable` flag (1 for on, 0 for off).

#### FailClose (`failclose`)
*   `enable`: (0/1) Enable FailClose toggling.
*   `interval`: Iteration frequency to toggle FailClose settings.

#### Client Disabling (`client_disabling`)
*   `enable`: (0/1) If 1, runs a background thread that randomly enables/disables the client using `nsdiag`.
*   `enable_sec_min`: Minimum duration (seconds) to keep the client **ENABLED** before toggling (Valid: 180-600).
*   `enable_sec_max`: Maximum duration (seconds) to keep the client **ENABLED** before toggling (Valid: 600-1200).
*   `disable_ratio`: Ratio of disable duration relative to the enable duration (Valid: 0.0-1.0).
    *   *Example*: If enabled for 200s and ratio is 0.15, it will disable for 30s.

#### WebUI Login (`webui_login`)
*   `tenant_username`: NetSkope Tenant Username for login simulation.

#### WebUI On-Prem (`webui_on_prem`)
*   `enable`: (0/1) Enable On-Prem WebUI features.
*   `onprem_use_dns`: (0/1) Toggle using DNS for On-Prem setup.
*   `onprem_http_host`: Host URL for On-Prem simulation.

#### WebUI TLS/DTLS Toggle (`webui_tls_dtls_toggle`)
*   `enable`: (0/1) Enable periodic tunnel protocol toggling between TLS and DTLS via WebUI API.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.

#### WebUI Steering Mode Toggle (`webui_steering_mode_toggle`)
*   `enable`: (0/1) Enable periodic steering mode toggling between "web" and "all" via WebUI API.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.

#### WebUI FailClose Toggle (`webui_failclose_toggle`)
*   `enable`: (0/1) Enable periodic failClose toggling via WebUI API (tenant-level, not local hosts file).
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.

#### WebUI SNI Toggle (`webui_sni_toggle`)
*   `enable`: (0/1) Enable periodic SNI checking toggle via WebUI API.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.

#### WebUI Exception Domains Toggle (`webui_exception_domains_toggle`)
*   `enable`: (0/1) Enable periodic adding/removing of exception domains from steering config.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.
*   `exception_domains`: List of domain strings to add/remove (e.g., `["test1.com", "test2.com"]`).

#### WebUI Client Disabling Toggle (`webui_client_disabling_toggle`)
*   `enable`: (0/1) Enable periodic toggling of `allowClientDisabling` via WebUI API.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.

#### WebUI Custom Ports Toggle (`webui_custom_ports_toggle`)
*   `enable`: (0/1) Enable periodic adding/removing of custom steered ports from steering config.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.
*   `custom_ports`: List of port objects, each with `ports`, `domains`, and `description` fields.
    *   Example: `[{"ports": "9501", "domains": "portquiz.net", "description": "stress_test_port"}]`

#### WebUI Interop Proxy Toggle (`webui_interop_proxy_toggle`)
*   `enable`: (0/1) Enable periodic toggling of interopProxy via WebUI API.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.
*   `host`: Proxy hostname/IP to use when enabling interop proxy.
*   `port`: Proxy port to use when enabling interop proxy.

#### WebUI MTU Toggle (`webui_mtu_toggle`)
*   `enable`: (0/1) Enable periodic MTU value cycling via WebUI API.
*   `interval`: Iteration frequency to toggle. Requires `webui_login` credentials.
*   `mtu_values`: List of MTU values to cycle through (e.g., `[1400, 1200, 800, ""]`). Empty string `""` resets to default.

### Power Tests (power_test)

Controls AOAC power behaviors. Settings moved out of `client_feature_toggling`.
Backward compatibility: if `power_test` is missing, legacy `client_feature_toggling` AOAC
entries are still honored.

#### AOAC S0 Standby (`aoac_s0_standby`)
*   `enable`: (0/1) Enable system sleep triggers (S0 Low Power Idle).
*   `interval`: Iteration frequency to trigger system sleep.
*   `duration_sec`: Duration in seconds to stay in sleep mode before waking.

#### AOAC S1 Standby (`aoac_s1_standby`)
*   `enable`: (0/1) Enable system sleep triggers (S1 Standby).
*   `interval`: Iteration frequency to trigger system sleep.
*   `duration_sec`: Duration in seconds to stay in sleep mode before waking.

#### AOAC S4 Hibernate (`aoac_s4_hibernate`)
*   `enable`: (0/1) Enable system hibernation triggers (S4).
*   `interval`: Iteration frequency to trigger system hibernation.
*   `duration_sec`: Duration in seconds to stay in hibernation before waking.

### Traffic Generation Settings (traffic_gen)

All traffic modules support `duration_sec` and `count`. If `duration_sec` > 0, it takes precedence over `count`.

#### Browser (`browser`)
*   `enable`: (0/1) If 1, enables the browser tab opening feature based on memory usage.
*   `max_memory`: System memory threshold (50-99%). If exceeded, browser tabs stop opening.
*   `max_tabs`: Maximum number of concurrent browser tabs allowed.
*   `log_validation`: (0/1) Enable validation of browser traffic logs (Requires valid steering config).

#### HTTPS Flood (`https`)
*   `enable`: (0/1) Enable HTTPS traffic generation using curl.
*   `duration_sec`: Duration to run the flood.
*   `count`: Number of requests (if duration is 0).
*   `concurrent_conn`: Number of concurrent threads.
*   `log_validation`: (0/1) Enable validation of curl traffic logs.
*   `log_validation_ratio`: Percentage (0-100) of curl requests to validate (to reduce overhead).
*   **Note:** runs in insecure mode (`-k`), ignoring SSL certificate validation errors.

#### DNS Flood (`dns`)
*   `enable`: (0/1) Enable random subdomain queries to bypass local DNS cache.
*   `duration_sec`: Duration to run the flood.
*   `count`: Number of queries (if duration is 0).
*   `concurrent_conn`: Number of concurrent threads.

#### FTP/FTPS/SFTP Traffic (`ftp`, `ftps`, `sftp`)
Each protocol has its own section in `config.json` with similar fields:
*   `enable`: (0/1) Enable traffic generation.
*   `target_ip`: Target server IP.
*   `target_port`: Target server port (Default: FTP 21, FTPS 990, SFTP 2222).
*   `user`: Username for authentication.
*   `password`: Password for authentication.
*   `file_size_mb`: Size of the file to upload in MB (generated in memory).
*   `duration_sec`: Duration to run the upload loop.
*   `count`: Number of uploads (if duration is 0).
*   `concurrent_conn`: Number of concurrent upload threads.

#### UDP Flood (`udp`)
*   `enable`: (0/1) Enable UDP packet flooding.
*   `duration_sec`: Duration to sustain the UDP flood.
*   `count`: Number of packets (if duration is 0).
*   `concurrent_conn`: Number of concurrent threads.
*   `target_ip`: Target IPv4 address.
*   `target_ipv6`: Target IPv6 address (Optional).
*   `target_port`: Target UDP port.

#### Apache Benchmark (`ab`)
*   `enable`: (0/1) Enable Apache Benchmark stress testing.
*   `duration_sec`: Duration to run the test.
*   `total_conn`: Total number of requests (if duration is 0).
*   `concurrent_conn`: Number of concurrent requests.
*   `target_urls`: List of URLs to target.

#### HTTPS Flood (`https`)
*   `enable`: (0/1) If 1, enables high-concurrency HTTP requests using curl.
*   `count`: (int) Total number of curl requests to send.
*   `duration_sec`: Duration to run the test.
*   `concurrent_conn`: (int) Number of concurrent curl processes.

`long_idle_interval`: Iteration frequency to trigger a long idle period (useful for soak testing).
* If set to **> 0**: Sleeps for `long_idle_time_min` to `long_idle_time_max` seconds every N iterations.
* If set to **0**: Randomly sleeps for **30 to 120 seconds** in *every* iteration.

`long_idle_time_min`: Minimum duration for the long idle in seconds (Lower bound: 300s).

`long_idle_time_max`: Maximum duration for the long idle in seconds (Upper bound: 7200s).

**Strategy 1: Memory & Handle Leak Detection**
* * The main idea is NOT to stop client service and keep it running but open/close the browser tabs.
* * Then check the resource usage.

```json
{
    "loop_times": 3000,
    "stop_svc_interval": 0,
    "stop_drv_interval": 0,
    "client_feature_toggling": {
        "failclose": { "enable": 0, "interval": 0 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 0, "interval": 0, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 90,
            "max_tabs": 50
        }
    }
}
```

**Strategy 2: Application Crash Stress (User Mode)**
* * The main idea is to stop the user mode service `stAgentSvc` in each iteration.
* * As different feature flags are enabled, we can know more about the stability of certian features.

```json
{
    "loop_times": 1000,
    "stop_svc_interval": 1,
    "stop_drv_interval": 0,
    "client_feature_toggling": {
        "failclose": { "enable": 1, "interval": 50 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 0, "interval": 0, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "long_idle_interval": 0,
    "long_idle_time_min": 300,
    "long_idle_time_max": 300,
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 80,
            "max_tabs": 30
        }
    }
}
```

**Strategy 3: Blue Screen Detection**
* * Try to stop the driver every few iterations and see of BSOD occurs.
* * If it happens, please collect C:\Windows\memory.dmp

* * Hint: DO NOT restart the driver in each loop.

```json
{

    "loop_times": 1000,
    "stop_svc_interval": 1,
    "stop_drv_interval": 1,
    "client_feature_toggling": {
        "failclose": { "enable": 1, "interval": 50 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 0, "interval": 0, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "long_idle_interval": 0,
    "long_idle_time_min": 300,
    "long_idle_time_max": 300,
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 80,
            "max_tabs": 30
        }
    }
}
```

**Strategy 4: Soak Mode**
* * With very limited resource using for a long term with longer sleep time.
* * So we give a big loop_times and longer `long_idle_time`.

```json
{

    "loop_times": 9000,
    "stop_svc_interval": 0,
    "stop_drv_interval": 0,
    "client_feature_toggling": {
        "failclose": { "enable": 1, "interval": 100 },
        "client_disabling": { "enable": 0 },
        "aoac_sleep": { "enable": 1, "interval": 1, "duration_sec": 60 }
    },
    "custom_dump_path": "",
    "long_idle_interval": 1,
    "long_idle_time_min": 1000,
    "long_idle_time_max": 3600,
    "traffic_gen": {
        "browser": {
            "enable": 1,
            "max_memory": 60,
            "max_tabs": 10
        }
    }
}
```

**Strategy 5: High Concurrency / Traffic Stress**
* * Uses internal Python generators for DNS/UDP and ab.exe for TCP connections.
* * If you do not use a real HTTP server, keep `ab` -> `concurrent_conn` lower then 500.

```json
{
  "loop_times": 1000,
  "stop_svc_interval": 5,
  "stop_drv_interval": 0,
  "client_feature_toggling": {
    "failclose": {
      "enable": 1,
      "interval": 15
    },
    "client_disabling": {
      "enable": 0,
      "enable_sec_min": 180,
      "enable_sec_max": 600,
      "disable_ratio": 0.15
    },
    "aoac_sleep": {
      "enable": 0,
      "interval": 0,
      "duration_sec": 60
    }
  },
  "custom_dump_path": "C:\dump\stAgentSvc.exe\*.dmp",
  "long_idle_interval": 100,
  "long_idle_time_min": 300,
  "long_idle_time_max": 600,
  "traffic_gen": {
    "browser": {
      "enable": 1,
      "max_memory": 60,
      "max_tabs": 20
    },
    "dns": {
      "enable": 1,
      "count": 500,
      "duration_sec": 0,
      "concurrent_conn": 20
    },
    "udp": {
      "enable": 1,
      "target_ip": "192.168.1.2",
      "target_ipv6": "",
      "target_port": 8080,
      "duration_sec": 20,
      "count": 0,
      "concurrent_conn": 10
    },
    "ab": {
      "enable": 1,
      "total_conn": 10000,
      "concurrent_conn": 256,
      "duration_sec": 0,
      "target_urls": [
        "http://10.1.2.3"
      ]
    },
    "https": {
      "enable": 1,
      "count": 1000,
      "duration_sec": 0,
      "concurrent_conn": 50
    }
  }
}
```

