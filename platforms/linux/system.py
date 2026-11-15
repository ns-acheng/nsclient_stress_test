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
        """Get PID of a process by name using psutil."""
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
        """Log process CPU and memory usage using ps command."""
        try:
            # Use ps -C to get CPU usage sum for all instances of the process
            result = subprocess.run(
                ["ps", "-C", process_name, "-o", "%cpu,rss", "--no-headers"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0 or not result.stdout.strip():
                return False

            # Parse ps output and sum CPU values (for multiple instances)
            lines = [l.strip() for l in result.stdout.split('\n') if l.strip()]
            total_cpu = 0.0
            total_mem_kb = 0.0

            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        total_cpu += float(parts[0])
                        total_mem_kb += float(parts[1])
                    except ValueError:
                        pass

            mem_mb = total_mem_kb / 1024.0

            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            full_path = os.path.join(log_dir, f"{process_name}_resources.log")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(full_path, "a", encoding='utf-8') as f:
                f.write(f"{now_str}, {total_cpu:.1f}%, {mem_mb:.1f}MB\n")

            return True

        except subprocess.TimeoutExpired:
            logger.warning(f"ps command timed out for {process_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to log process usage for {process_name}: {e}")
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

    def generate_resource_summary(self, process_names: list, log_dir: str) -> bool:
        """Generate unified summary report for all monitored processes."""
        try:
            if not os.path.exists(log_dir):
                return False

            summary_path = os.path.join(log_dir, "resource_summary.log")

            # Read and parse all individual process logs
            all_data = {}
            for process_name in process_names:
                log_path = os.path.join(log_dir, f"{process_name}_resources.log")
                if not os.path.exists(log_path):
                    continue

                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if not lines:
                        continue

                    cpu_values = []
                    mem_values = []
                    for line in lines:
                        parts = line.strip().split(', ')
                        if len(parts) >= 3:
                            try:
                                cpu_str = parts[1].replace('%', '')
                                mem_str = parts[2].replace('MB', '')
                                cpu_values.append(float(cpu_str))
                                mem_values.append(float(mem_str))
                            except ValueError:
                                pass

                    if cpu_values and mem_values:
                        all_data[process_name] = {
                            'samples': len(cpu_values),
                            'cpu_avg': sum(cpu_values) / len(cpu_values),
                            'cpu_max': max(cpu_values),
                            'cpu_min': min(cpu_values),
                            'mem_avg': sum(mem_values) / len(mem_values),
                            'mem_max': max(mem_values),
                            'mem_min': min(mem_values),
                        }

            if not all_data:
                logger.warning("No resource data available for summary")
                return False

            # Write unified summary
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("RESOURCE USAGE SUMMARY - ALL PROCESSES\n")
                f.write("=" * 80 + "\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                for process_name, stats in all_data.items():
                    f.write(f"Process: {process_name}\n")
                    f.write("-" * 80 + "\n")
                    f.write(f"  Samples Collected: {stats['samples']}\n")
                    f.write(f"  CPU Usage:\n")
                    f.write(f"    Average: {stats['cpu_avg']:.1f}%\n")
                    f.write(f"    Maximum: {stats['cpu_max']:.1f}%\n")
                    f.write(f"    Minimum: {stats['cpu_min']:.1f}%\n")
                    f.write(f"  Memory Usage:\n")
                    f.write(f"    Average: {stats['mem_avg']:.1f} MB\n")
                    f.write(f"    Maximum: {stats['mem_max']:.1f} MB\n")
                    f.write(f"    Minimum: {stats['mem_min']:.1f} MB\n")
                    f.write("\n")

                # Overall statistics
                total_samples = sum(s['samples'] for s in all_data.values())
                total_cpu_avg = sum(s['cpu_avg'] for s in all_data.values())
                total_mem_avg = sum(s['mem_avg'] for s in all_data.values())

                f.write("=" * 80 + "\n")
                f.write("OVERALL STATISTICS\n")
                f.write("=" * 80 + "\n")
                f.write(f"  Total Samples: {total_samples}\n")
                f.write(f"  Combined Average CPU: {total_cpu_avg:.1f}%\n")
                f.write(f"  Combined Average Memory: {total_mem_avg:.1f} MB\n")
                f.write("=" * 80 + "\n")

            logger.info(f"Resource summary generated: {summary_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate resource summary: {e}")
            return False
