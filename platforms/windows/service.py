import time
import logging
import psutil
import subprocess
import os
from interfaces.i_service import IServiceManager
from platforms.windows.diag import WindowsDiagnostics # For live dump

logger = logging.getLogger()

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
            subprocess.run(["sc", "start", service_name], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start {service_name}: {e}")
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
