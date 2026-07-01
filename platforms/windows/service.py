import time
import logging
import psutil
import subprocess
import os
from interfaces.i_service import IServiceManager
from platforms.windows.diag import WindowsDiagnostics # For live dump

logger = logging.getLogger()

SERVICE_START_TIMEOUT_SEC = 90
SERVICE_STATUS_POLL_SEC = 1

class WindowsServiceManager(IServiceManager):
    def get_service_status(self, service_name: str) -> str:
        try:
            status = subprocess.check_output(
                ["sc", "query", service_name],
                encoding='utf-8',
                errors='replace'
            )
            if "RUNNING" in status:
                return "RUNNING"
            elif "STOPPED" in status:
                return "STOPPED"
            elif "STOP_PENDING" in status:
                return "STOP_PENDING"
            elif "START_PENDING" in status:
                return "START_PENDING"
            return "UNKNOWN"
        except subprocess.CalledProcessError:
            return "NOT_FOUND"

    def start_service(self, service_name: str) -> bool:
        try:
            logger.info(f"Starting service '{service_name}'...")
            result = subprocess.run(
                ["sc", "start", service_name],
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30,
            )
            if result.stdout.strip():
                logger.info(result.stdout.strip())
            if result.stderr.strip():
                logger.warning(result.stderr.strip())
            return self._wait_for_target_status(
                service_name,
                "RUNNING",
                SERVICE_START_TIMEOUT_SEC,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start {service_name}: {e}")
            return False
        except subprocess.TimeoutExpired:
            logger.error(
                f"Timeout while issuing start command for {service_name}."
            )
            return False

    def _wait_for_target_status(
        self,
        service_name: str,
        target_status: str,
        timeout: int,
    ) -> bool:
        start_time = time.monotonic()
        last_status = None
        last_progress_log = -1

        while time.monotonic() - start_time < timeout:
            elapsed = int(time.monotonic() - start_time)
            status = self.get_service_status(service_name)
            if status == target_status:
                logger.info(
                    f"Service '{service_name}' reached {target_status} "
                    f"after {elapsed}s."
                )
                return True

            if status != last_status or elapsed // 10 > last_progress_log:
                logger.info(
                    f"Service '{service_name}' status after start: {status} "
                    f"({elapsed}s elapsed)"
                )
                last_status = status
                last_progress_log = elapsed // 10

            time.sleep(SERVICE_STATUS_POLL_SEC)

        final_status = self.get_service_status(service_name)
        logger.error(
            f"Timeout waiting for service '{service_name}' to reach "
            f"{target_status}. Final status: {final_status}"
        )
        return False

    def stop_service(self, service_name: str, timeout: int = 30) -> bool:
        try:
            logger.info(f"Stopping service '{service_name}'...")
            subprocess.run(["sc", "stop", service_name], check=False)

            if timeout == 0:
                return True

            for _ in range(timeout):
                status = self.get_service_status(service_name)
                if status == "STOPPED":
                    logger.info(f"Service '{service_name}' stopped successfully.")
                    return True
                time.sleep(1)

            logger.error(f"Error: Timeout. Service '{service_name}' did not stop within {timeout}s.")
            return False
        except Exception as e:
            logger.error(f"Exception stopping {service_name}: {e}")
            return False

    def handle_non_stop(self, service_name: str, is_64bit: bool, log_dir: str) -> None:
        logger.warning(f"Handling non-stop for '{service_name}'. Waiting extra 60s...")
        for i in range(60):
            status = self.get_service_status(service_name)
            if status == "STOPPED":
                logger.info(f"Service '{service_name}' finally stopped after {i+1}s extra wait.")
                return
            time.sleep(1)

        logger.error(f"Service '{service_name}' IS STILL RUNNING/HANGING after extra wait.")
        
        proc_name = "stAgentSvc.exe"
        if "stagent" not in service_name.lower():
            proc_name = f"{service_name}.exe"
        
        # We need a way to get PID and dump. Using psutil locally here.
        pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] and proc.info['name'].lower() == proc_name.lower():
                pid = proc.info['pid']
                break
        
        diag = WindowsDiagnostics() # Use the diag impl
        if pid:
            diag.generate_live_dump(pid, log_dir)
        else:
            logger.error(f"Could not find PID for {proc_name} to dump.")

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        diag.collect_log_bundle(timestamp, is_64bit, log_dir)
        logger.info("Live dump and logs collected. Returning to stop testing.")
