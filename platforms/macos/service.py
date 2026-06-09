import subprocess
import logging
import time
import os
import signal
from interfaces.i_service import IServiceManager

logger = logging.getLogger()

class MacOSServiceManager(IServiceManager):
    def _run_launchctl(self, args: list) -> tuple[int, str]:
        # Wraps launchctl. Note: modern macOS uses `launchctl bootout` / `bootstrap` 
        # but `load`/`unload` / `start`/`stop` often still work for legacy or specific domains.
        # We assume the service_name is the label (e.g. com.netskope.stagentsvc)
        cmd = ["launchctl"] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode, res.stdout
        except Exception as e:
            return -1, str(e)

    def get_service_status(self, service_name: str) -> str:
        # launchctl list | grep service_name
        # output format: PID  Status  Label
        cmd = ["launchctl", "list"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            for line in res.stdout.splitlines():
                if service_name in line:
                    parts = line.split()
                    if parts[0].isdigit(): # PID exists
                        return "RUNNING"
                    return "STOPPED"
            return "NOT_FOUND" 
        except:
            return "UNKNOWN"

    def start_service(self, service_name: str) -> bool:
        logger.info(f"Starting service '{service_name}'...")
        # Try 'start' command first (for loaded jobs)
        rc, out = self._run_launchctl(["start", service_name])
        if rc == 0: return True
        # If not loaded, might need 'load'. But we need path for load.
        # Assuming simple start for now or that it's already loaded.
        logger.error(f"Failed to start {service_name}: {out}")
        return False

    def stop_service(self, service_name: str, timeout: int = 30) -> bool:
        logger.info(f"Stopping service '{service_name}'...")
        self._run_launchctl(["stop", service_name])
        
        if timeout == 0:
            return True

        for _ in range(timeout):
            status = self.get_service_status(service_name)
            if status == "STOPPED":
                logger.info(f"Service '{service_name}' stopped successfully.")
                return True
            time.sleep(1)
            
        logger.error(f"Timeout stopping {service_name}")
        return False

    def handle_non_stop(self, service_name: str, is_64bit: bool, log_dir: str) -> None:
        logger.warning(f"Handling non-stop for {service_name}")
        pid = self._get_pid_by_name(service_name)
        if pid:
            try:
                os.kill(pid, signal.SIGKILL)
                logger.info(f"Killed PID {pid}")
            except:
                pass
        
    def _get_pid_by_name(self, name: str) -> int:
        try:
            res = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True)
            if res.stdout.strip():
                return int(res.stdout.splitlines()[0])
        except:
            pass
        return 0
