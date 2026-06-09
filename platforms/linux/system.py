import os
import subprocess
import logging
import psutil
from datetime import datetime
from interfaces.i_system import ISystemInfo

logger = logging.getLogger()

class LinuxSystemInfo(ISystemInfo):
    """Linux system information implementation."""

    def get_process_pid(self, process_name: str) -> int:
        """Get PID of a process by name."""
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] == process_name:
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return 0

    def get_memory_usage(self) -> tuple[int, int]:
        """Get system memory usage (percent, available_mb)."""
        try:
            mem = psutil.virtual_memory()
            return (int(mem.percent), int(mem.available / (1024*1024)))
        except Exception:
            return (0, 0)

    def enable_privilege(self, privilege_name: str) -> int:
        """Check for root privileges on Linux."""
        if os.geteuid() != 0:
            logger.warning("Not running as root! Some functions may fail.")
            return 1
        return 0

    def log_process_usage(self, process_name: str, log_dir: str) -> bool:
        """Log process CPU and memory usage."""
        pid = self._get_pid(process_name)
        if not pid:
            return False

        try:
            # Use ps command to get CPU and memory info
            cmd = ["ps", "-p", str(pid), "-o", "%cpu,rss"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            lines = res.stdout.strip().splitlines()

            if len(lines) > 1:
                vals = lines[1].strip().split()
                if len(vals) >= 2:
                    cpu = float(vals[0])
                    rss_kb = int(vals[1])
                    rss_mb = rss_kb / 1024

                    if not os.path.exists(log_dir):
                        os.makedirs(log_dir)
                    full_path = os.path.join(log_dir, f"{process_name}_resources.log")
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    with open(full_path, "a", encoding='utf-8') as f:
                        f.write(f"{now_str}, {cpu:.1f}%, {rss_mb:.1f}MB, {rss_kb}KB, 0\n")
                    return True
        except Exception as e:
            logger.error(f"Failed to log process usage: {e}")
        return False

    def _get_pid(self, name: str) -> int:
        """Get PID using pgrep command."""
        try:
            res = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True)
            if res.stdout.strip():
                return int(res.stdout.splitlines()[0])
        except Exception:
            pass
        return 0

    def set_startup_task(self, task_name: str, command: str) -> bool:
        """Create a systemd service for startup task."""
        service_name = f"{task_name}.service"
        service_path = f"/etc/systemd/system/{service_name}"

        service_content = f"""[Unit]
Description={task_name}
After=network.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c '{command}'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

        try:
            if os.geteuid() != 0:
                logger.error("Writing to /etc/systemd/system requires root privileges. Run as root.")
                return False
            # Write service file
            with open(service_path, "w", encoding="utf-8") as f:
                f.write(service_content)

            # Reload systemd and enable service
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            subprocess.run(["sudo", "systemctl", "enable", service_name], check=True)
            logger.info(f"Created systemd service: {service_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create startup task: {e}")
            return False

    def remove_startup_task(self, task_name: str) -> None:
        """Remove systemd startup service."""
        service_name = f"{task_name}.service"
        service_path = f"/etc/systemd/system/{service_name}"

        try:
            if os.path.exists(service_path):
                subprocess.run(["sudo", "systemctl", "disable", service_name],
                             stderr=subprocess.DEVNULL, check=False)
                subprocess.run(["sudo", "systemctl", "stop", service_name],
                             stderr=subprocess.DEVNULL, check=False)
                os.remove(service_path)
                subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)
                logger.info(f"Removed startup task: {service_name}")
        except Exception as e:
            logger.error(f"Failed to remove startup task: {e}")

    def run_shell_script(self, script_path: str, args: list = None) -> None:
        """Execute a shell script."""
        cmd = ["/bin/bash", script_path]
        if args:
            cmd.extend(args)
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        logger.info(line)
            if result.stderr:
                for line in result.stderr.strip().split('\n'):
                    if line.strip():
                        logger.warning(line)
        except subprocess.CalledProcessError as e:
            logger.error(f"Shell script failed with return code {e.returncode}")
            if e.stdout:
                logger.error(f"stdout: {e.stdout}")
            if e.stderr:
                logger.error(f"stderr: {e.stderr}")
        except Exception as e:
            logger.error(f"Shell script failed: {e}")
