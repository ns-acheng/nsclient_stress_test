import glob
import logging
import os
import shutil
import datetime
import subprocess
from interfaces.i_diag import IDiagnostics

logger = logging.getLogger()

class LinuxDiagnostics(IDiagnostics):
    """Linux diagnostics implementation for Netskope client."""

    def __init__(self):
        self.nsdiag_path = "/opt/netskope/stagent/nsdiag"

    def _get_dump_paths(self, custom_dump_path: str = "") -> list[str]:
        """Get Linux crash dump locations."""
        paths = [
            "/var/crash/*netskope*",
            "/var/crash/*stagent*",
            "/var/log/netskope/stagent/core*",
            "/tmp/core*",
        ]
        if custom_dump_path:
            paths.append(custom_dump_path)
        return paths

    def check_crash_dumps(self, custom_dump_path: str = "") -> tuple[bool, int]:
        """Check for crash dumps in Linux standard locations."""
        paths = self._get_dump_paths(custom_dump_path)
        found = False
        for path in paths:
            files = glob.glob(path)
            if files:
                logger.error(f"Crash dump found: {files[0]}")
                found = True
        return found, 0

    def collect_log_bundle(self, timestamp: str, is_64bit: bool, output_dir: str) -> None:
        """Collect diagnostic logs using nsdiag tool."""
        if os.path.exists(self.nsdiag_path):
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            out = os.path.join(output_dir, f"{timestamp}_bundle.tar.gz")
            try:
                subprocess.run(["sudo", self.nsdiag_path, "-o", out], check=False)
                logger.info(f"Log bundle created: {out}")
            except Exception as e:
                logger.error(f"Failed to collect log bundle: {e}")
        else:
            logger.warning(f"nsdiag tool not found at {self.nsdiag_path}")

    def sync_client_config(self, is_64bit: bool) -> None:
        """Sync client configuration using nsdiag."""
        if os.path.exists(self.nsdiag_path):
            try:
                subprocess.run(["sudo", self.nsdiag_path, "-u"], check=False)
                logger.info("Client config synced")
            except Exception as e:
                logger.error(f"Failed to sync config: {e}")

    def enable_client_tracing(self, enable: bool, is_64bit: bool) -> None:
        """Enable or disable client tracing."""
        if os.path.exists(self.nsdiag_path):
            act = "enable" if enable else "disable"
            try:
                subprocess.run(["sudo", self.nsdiag_path, "-t", act], check=False)
                logger.info(f"Client tracing {act}d")
            except Exception as e:
                logger.error(f"Failed to {act} tracing: {e}")

    def handle_crash(self, is_64bit: bool, log_dir: str, custom_dump_path: str = "") -> None:
        """Handle crash by collecting logs and dumps."""
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
        """Generate a live dump of a process using gdb or gcore."""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = os.path.join(output_dir, f"LiveDump_{pid}_{timestamp}.core")
        logger.info(f"Generating live dump for PID {pid} -> {dump_file}")

        try:
            # Try gcore first (part of gdb package)
            result = subprocess.run(
                ["gcore", "-o", dump_file, str(pid)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info("Live dump generated successfully using gcore.")
            else:
                logger.error(f"gcore failed with RC {result.returncode}: {result.stderr}")
        except FileNotFoundError:
            # gcore not available, try gdb
            logger.warning("gcore not found, attempting with gdb...")
            try:
                result = subprocess.run(
                    ["gdb", "-batch", "-ex", f"attach {pid}", "-ex", f"gcore {dump_file}",
                     "-ex", "detach", "-ex", "quit"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    logger.info("Live dump generated successfully using gdb.")
                else:
                    logger.error(f"gdb failed with RC {result.returncode}: {result.stderr}")
            except Exception as e:
                logger.error(f"Failed to generate live dump with gdb: {e}")
        except subprocess.TimeoutExpired:
            logger.error(f"Live dump command timed out for PID {pid}")
        except Exception as e:
            logger.error(f"Failed to generate live dump: {e}")
