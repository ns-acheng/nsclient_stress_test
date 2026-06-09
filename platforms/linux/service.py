import subprocess
import logging
import time
import os
import signal
from interfaces.i_service import IServiceManager

logger = logging.getLogger()

class LinuxServiceManager(IServiceManager):
    """Linux service manager using systemctl."""

    def _run_systemctl(self, args: list) -> tuple[int, str]:
        """Execute systemctl command."""
        cmd = ["systemctl"] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            return res.returncode, res.stdout + res.stderr
        except Exception as e:
            return -1, str(e)

    def get_service_status(self, service_name: str) -> str:
        """
        Get service status using systemctl.

        Returns:
            "RUNNING" if service is active
            "STOPPED" if service is inactive/failed
            "NOT_FOUND" if service doesn't exist
            "UNKNOWN" on error
        """
        rc, out = self._run_systemctl(["is-active", service_name])

        # systemctl is-active returns:
        # 0 if active, 3 if inactive/failed, 4 if not found
        if rc == 0:
            return "RUNNING"
        elif rc == 3:
            return "STOPPED"
        elif rc == 4:
            return "NOT_FOUND"
        else:
            # Check if service exists by trying to get status
            rc_status, _ = self._run_systemctl(["status", service_name])
            if "could not be found" in _.lower() or "not loaded" in _.lower():
                return "NOT_FOUND"
            return "UNKNOWN"

    def start_service(self, service_name: str) -> bool:
        """Start a systemd service."""
        logger.info(f"Starting service '{service_name}'...")
        rc, out = self._run_systemctl(["start", service_name])

        if rc == 0:
            logger.info(f"Service '{service_name}' started successfully.")
            return True
        else:
            logger.error(f"Failed to start {service_name}: {out}")
            return False

    def stop_service(self, service_name: str, timeout: int = 30) -> bool:
        """
        Stop a systemd service.

        Args:
            service_name: Name of the service
            timeout: Seconds to wait for service to stop (0 = no wait)

        Returns:
            True if service stopped successfully, False otherwise
        """
        logger.info(f"Stopping service '{service_name}'...")
        rc, out = self._run_systemctl(["stop", service_name])

        if rc != 0:
            logger.error(f"Failed to stop {service_name}: {out}")
            return False

        if timeout == 0:
            return True

        # Wait for service to stop
        for _ in range(timeout):
            status = self.get_service_status(service_name)
            if status == "STOPPED":
                logger.info(f"Service '{service_name}' stopped successfully.")
                return True
            time.sleep(1)

        logger.error(f"Timeout stopping {service_name}")
        return False

    def handle_non_stop(self, service_name: str, is_64bit: bool, log_dir: str) -> None:
        """
        Handle service that won't stop gracefully.

        Attempts to forcefully kill the service process.
        """
        logger.warning(f"Handling non-stop service: {service_name}")

        # Try to get the main PID from systemctl
        rc, out = self._run_systemctl(["show", service_name, "--property=MainPID"])
        pid = 0

        if rc == 0:
            # Parse MainPID=<pid>
            for line in out.splitlines():
                if line.startswith("MainPID="):
                    try:
                        pid = int(line.split("=")[1])
                        break
                    except (ValueError, IndexError):
                        pass

        # If we got a PID, kill it
        if pid > 0:
            try:
                logger.info(f"Sending SIGKILL to PID {pid}")
                os.kill(pid, signal.SIGKILL)
                time.sleep(2)
            except ProcessLookupError:
                logger.info(f"Process {pid} already terminated")
            except PermissionError:
                logger.error(f"Permission denied to kill PID {pid}")
            except Exception as e:
                logger.error(f"Failed to kill PID {pid}: {e}")
        else:
            # Fallback: strip .service suffix so pgrep matches the actual process name
            lookup_name = service_name[:-8] if service_name.endswith(".service") else service_name
            pid = self._get_pid_by_name(lookup_name)
            if pid:
                try:
                    os.kill(pid, signal.SIGKILL)
                    logger.info(f"Killed process {lookup_name} (PID {pid})")
                except Exception as e:
                    logger.error(f"Failed to kill process: {e}")

    def _get_pid_by_name(self, name: str) -> int:
        """Get PID using pgrep command."""
        try:
            res = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True)
            if res.stdout.strip():
                return int(res.stdout.splitlines()[0])
        except Exception:
            pass
        return 0
