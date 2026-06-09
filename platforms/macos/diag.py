import glob
import logging
import os
import shutil
import datetime
import subprocess
from interfaces.i_diag import IDiagnostics

logger = logging.getLogger()

class MacOSDiagnostics(IDiagnostics):
    def __init__(self):
        self.nsdiag_path = os.path.expanduser("~/Library/Application Support/Netskope/STAgent/nsdiag")

    def _get_dump_paths(self, custom_dump_path: str = "") -> list[str]:
        base_path = os.path.expanduser("~/Library/Logs/DiagnosticReports")
        paths = [
            os.path.join(base_path, "Netskope Client*.ips"),
            os.path.join(base_path, "nsdiag*.ips")
        ]
        if custom_dump_path:
            paths.append(custom_dump_path)
        return paths

    def check_crash_dumps(self, custom_dump_path: str = "") -> tuple[bool, int]:
        paths = self._get_dump_paths(custom_dump_path)
        found = False
        for path in paths:
            files = glob.glob(path)
            if files:
                logger.error(f"Crash report found: {files[0]}")
                found = True
        return found, 0

    def collect_log_bundle(self, timestamp: str, is_64bit: bool, output_dir: str) -> None:
        if os.path.exists(self.nsdiag_path):
            if not os.path.exists(output_dir): os.makedirs(output_dir)
            out = os.path.join(output_dir, f"{timestamp}_bundle.zip")
            subprocess.run(["sudo", self.nsdiag_path, "-o", out])

    def sync_client_config(self, is_64bit: bool) -> None:
        if os.path.exists(self.nsdiag_path):
            subprocess.run(["sudo", self.nsdiag_path, "-u"])

    def enable_client_tracing(self, enable: bool, is_64bit: bool) -> None:
        if os.path.exists(self.nsdiag_path):
            act = "enable" if enable else "disable"
            subprocess.run(["sudo", self.nsdiag_path, "-t", act])

    def handle_crash(self, is_64bit: bool, log_dir: str, custom_dump_path: str = "") -> None:
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.info("Handling crash: Collecting logs and dumps...")
            self.collect_log_bundle(timestamp, is_64bit, log_dir)

            dump_paths = self._get_dump_paths(custom_dump_path)
            for path in dump_paths:
                files = glob.glob(path)
                for f in files:
                    if os.path.exists(f) and os.path.getsize(f) > 0:
                        try:
                            shutil.copy2(f, log_dir)
                            logger.info(f"Copied dump file {f} to {log_dir}")
                        except Exception as e:
                            logger.error(f"Failed to copy dump {f}: {e}")
        except Exception as e:
            logger.error(f"Error during crash handling: {e}")

    def generate_live_dump(self, pid: int, output_dir: str) -> None:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = os.path.join(output_dir, f"LiveDump_{pid}_{timestamp}.txt")
        logger.info(f"Generating live dump for PID {pid} -> {dump_file}")

        try:
            # Use sample command to capture process state
            result = subprocess.run(
                ["sample", str(pid), "1", "-file", dump_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info("Live dump generated successfully.")
            else:
                logger.error(f"Sample command failed with RC {result.returncode}: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error(f"Sample command timed out for PID {pid}")
        except Exception as e:
            logger.error(f"Failed to generate live dump: {e}")
