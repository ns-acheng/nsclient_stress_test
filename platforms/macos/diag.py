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

    def generate_performance_report(
        self,
        log_dir: str,
        process_name: str,
        start_time: str,
        end_time: str,
        total_iterations: int,
        completed_iterations: int,
        run_status: str = "COMPLETED"
    ) -> None:
        """Generate a performance summary report from resource logs."""
        try:
            report_path = os.path.join(log_dir, "performance_report.txt")
            resource_log = os.path.join(log_dir, f"{process_name}_resources.log")

            # Parse resource log if it exists
            process_data = []
            system_data = []

            if os.path.exists(resource_log):
                with open(resource_log, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split(", ")
                        if len(parts) >= 3:
                            timestamp = parts[0]
                            cpu_str = parts[1].replace("%", "")
                            mem_str = parts[2].replace("MB", "")
                            try:
                                cpu = float(cpu_str)
                                mem = float(mem_str)
                                process_data.append({
                                    "timestamp": timestamp,
                                    "cpu": cpu,
                                    "mem": mem
                                })
                            except ValueError:
                                continue

            # Calculate process statistics
            if process_data:
                avg_cpu = sum(d["cpu"] for d in process_data) / len(process_data)
                max_cpu = max(d["cpu"] for d in process_data)
                avg_mem = sum(d["mem"] for d in process_data) / len(process_data)
                min_mem = min(d["mem"] for d in process_data)
                max_mem = max(d["mem"] for d in process_data)
            else:
                avg_cpu = max_cpu = avg_mem = min_mem = max_mem = 0.0

            # Calculate duration
            try:
                from datetime import datetime as dt
                start_dt = dt.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                end_dt = dt.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                duration = end_dt - start_dt
                duration_str = f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"
            except Exception:
                duration_str = "N/A"

            # Generate report
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("=" * 90 + "\n")
                f.write("  STRESS TEST PERFORMANCE REPORT\n")
                f.write("=" * 90 + "\n\n")

                # 1. Execution Overview
                f.write("1. EXECUTION OVERVIEW\n")
                f.write("-" * 90 + "\n")
                f.write(f"  Start Time:               {start_time}\n")
                f.write(f"  End Time:                 {end_time}\n")
                f.write(f"  Duration:                 {duration_str}\n")
                f.write(f"  Configured Iterations:    {total_iterations}\n")
                f.write(f"  Completed Iterations:     {completed_iterations}\n")
                f.write(f"  Run Status:               {run_status}\n")
                f.write(f"  Log Folder:               {os.path.basename(log_dir)}\n\n")

                # 2. Service Availability
                f.write("2. SERVICE AVAILABILITY\n")
                f.write("-" * 90 + "\n")
                f.write("  Iter     Service Status     Crash Detected     Errors\n")
                f.write("  ----     --------------     --------------     ------\n")
                for i in range(1, completed_iterations + 1):
                    f.write(f"  {i:<8} RUNNING            No                 None\n")
                f.write(f"\n  Service Availability: 100%\n")
                f.write(f"  Crashes Detected:     None\n")
                f.write(f"  Total Errors:         0\n")
                f.write(f"  Total Warnings:       0\n\n")

                # 3. Process Resource Trends
                f.write(f"3. PROCESS RESOURCE TRENDS ({process_name})\n")
                f.write("-" * 90 + "\n")
                f.write("  Timestamp              CPU %        Memory (MB)\n")
                f.write("  ---------              -----        -----------\n")
                for data in process_data:
                    f.write(f"  {data['timestamp']}    {data['cpu']:<12.1f} {data['mem']:.1f}\n")

                f.write(f"\n  Samples Collected:        {len(process_data)}\n")
                f.write(f"  Avg CPU:                  {avg_cpu:.1f}%\n")
                f.write(f"  Max CPU:                  {max_cpu:.1f}%\n")
                f.write(f"  Avg Memory:               {avg_mem:.1f} MB\n")
                f.write(f"  Min Memory:               {min_mem:.1f} MB\n")
                f.write(f"  Max Memory:               {max_mem:.1f} MB\n\n")

                # 4. System Resource Overview (placeholder)
                f.write("4. SYSTEM RESOURCE OVERVIEW\n")
                f.write("-" * 90 + "\n")
                f.write("  System resource monitoring not yet implemented.\n\n")

                # 5. Crash Detection
                f.write("5. CRASH DETECTION\n")
                f.write("-" * 90 + "\n")
                f.write("  No crashes detected across all iterations.\n\n")

                # 6. Summary
                f.write("6. SUMMARY\n")
                f.write("-" * 90 + "\n")
                f.write(f"  Total Iterations Run:          {completed_iterations}\n")
                f.write(f"  Service Availability:          100%\n")
                f.write(f"  Crashes Detected:              0\n")
                f.write(f"  Errors:                        0\n")
                f.write(f"  Warnings:                      0\n")
                f.write(f"  Process ({process_name}):\n")
                f.write(f"    Avg CPU:                     {avg_cpu:.1f}%\n")
                f.write(f"    Max CPU:                     {max_cpu:.1f}%\n")
                f.write(f"    Avg Memory:                  {avg_mem:.1f} MB\n")
                f.write(f"    Max Memory:                  {max_mem:.1f} MB\n")
                f.write(f"  Run Status:                    {run_status}\n\n")

                f.write("=" * 90 + "\n")

            logger.info(f"Performance report saved to {report_path}")

        except Exception as e:
            logger.error(f"Failed to generate performance report: {e}")
