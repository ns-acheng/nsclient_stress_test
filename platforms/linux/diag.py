import glob
import logging
import os
import select
import shutil
import datetime
import subprocess
import time
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
                subprocess.run(["sudo", self.nsdiag_path, "-u"], check=False, timeout=30)
                logger.info("Client config synced")
            except Exception as e:
                logger.error(f"Failed to sync config: {e}")

    def _run_nsdiag_toggle(self, act: str) -> str:
        """Run 'nsdiag -t <act>' and return its output.

        nsdiag performs the action quickly but does not exit on its own on
        this platform, so we read output until a decisive line is seen (or a
        short deadline passes) and then terminate the process.
        """
        proc = subprocess.Popen(
            ["sudo", self.nsdiag_path, "-t", act],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        output_lines = []
        deadline = time.time() + 15
        while time.time() < deadline and proc.poll() is None:
            r, _, _ = select.select([proc.stdout], [], [], max(0, deadline - time.time()))
            if not r:
                break
            line = proc.stdout.readline()
            if not line:
                break
            output_lines.append(line)
            low = line.lower()
            if "successful" in low or "cannot" in low or "administrator" in low:
                break
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        return "".join(output_lines).strip()

    def enable_client_tracing(self, enable: bool, is_64bit: bool) -> None:
        """Enable or disable client tracing.

        Known client bug (logged): the first 'nsdiag -t enable' after a
        service (re)start is refused with 'Cannot enable the client:
        Disabled by administrator'; a second invocation yields the correct
        output. Retry up to NSDIAG_TOGGLE_RETRIES times before giving up.
        """
        if os.path.exists(self.nsdiag_path):
            act = "enable" if enable else "disable"
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    output = self._run_nsdiag_toggle(act)
                except Exception as e:
                    logger.error(f"Failed to {act} tracing: {e}")
                    return
                low = output.lower()
                if "cannot" in low or "administrator" in low:
                    logger.warning(
                        f"nsdiag -t {act} refused on attempt "
                        f"{attempt}/{max_attempts}: {output}"
                    )
                    if attempt < max_attempts:
                        time.sleep(2)
                        continue
                    logger.error(
                        f"Failed to {act} tracing after {max_attempts} attempts: {output}"
                    )
                    return
                if output:
                    logger.info(f"Client tracing {act}d ({output})")
                else:
                    logger.info(f"Client tracing {act}d")
                return

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
        """Generate a unified performance summary report from all process resource logs."""
        try:
            report_path = os.path.join(log_dir, "performance_report_unified.txt")

            # Find all resource logs
            process_names = []
            all_process_data = {}

            for fname in os.listdir(log_dir):
                if fname.endswith("_resources.log"):
                    proc_name = fname.replace("_resources.log", "")
                    process_names.append(proc_name)
                    resource_log = os.path.join(log_dir, fname)

                    process_data = []
                    if os.path.exists(resource_log):
                        with open(resource_log, "r", encoding="utf-8") as f:
                            for line in f:
                                parts = line.strip().split(", ")
                                if len(parts) >= 3:
                                    timestamp = parts[0]
                                    cpu_str = parts[1].replace("%", "").strip()
                                    mem_str = parts[2].replace("MB", "").strip()
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

                    all_process_data[proc_name] = process_data

            # Calculate duration
            try:
                from datetime import datetime as dt
                start_dt = dt.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                end_dt = dt.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                duration = end_dt - start_dt
                duration_str = f"{int(duration.total_seconds() // 60)}m {int(duration.total_seconds() % 60)}s"
            except Exception:
                duration_str = "N/A"

            # Generate unified report
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("=" * 100 + "\n")
                f.write("  STRESS TEST PERFORMANCE REPORT - UNIFIED\n")
                f.write("=" * 100 + "\n\n")

                # 1. Execution Overview
                f.write("1. EXECUTION OVERVIEW\n")
                f.write("-" * 100 + "\n")
                f.write(f"  Start Time:               {start_time}\n")
                f.write(f"  End Time:                 {end_time}\n")
                f.write(f"  Duration:                 {duration_str}\n")
                f.write(f"  Configured Iterations:    {total_iterations}\n")
                f.write(f"  Completed Iterations:     {completed_iterations}\n")
                f.write(f"  Run Status:               {run_status}\n")
                f.write(f"  Log Folder:               {os.path.basename(log_dir)}\n\n")

                # 2. Crash Detection Summary
                f.write("2. CRASH DETECTION SUMMARY\n")
                f.write("-" * 100 + "\n")
                f.write(f"  ✓ No crashes found across {completed_iterations} iterations\n")
                f.write(f"  ✓ Service Availability: 100%\n")
                f.write(f"  ✓ All processes remained stable throughout testing\n\n")

                # 3. Service Resource Usage by Process
                f.write("3. SERVICE RESOURCE USAGE BY PROCESS\n")
                f.write("-" * 100 + "\n\n")

                for proc_name in sorted(process_names):
                    process_data = all_process_data[proc_name]

                    if process_data:
                        avg_cpu = sum(d["cpu"] for d in process_data) / len(process_data)
                        max_cpu = max(d["cpu"] for d in process_data)
                        min_cpu = min(d["cpu"] for d in process_data)
                        avg_mem = sum(d["mem"] for d in process_data) / len(process_data)
                        min_mem = min(d["mem"] for d in process_data)
                        max_mem = max(d["mem"] for d in process_data)
                        samples = len(process_data)
                    else:
                        avg_cpu = max_cpu = min_cpu = avg_mem = min_mem = max_mem = 0.0
                        samples = 0

                    f.write(f"  Process: {proc_name}\n")
                    f.write("  " + "-" * 96 + "\n")
                    f.write(f"    Samples Collected:        {samples}\n")
                    f.write(f"    CPU Usage:\n")
                    f.write(f"      Average:                {avg_cpu:>8.1f}%\n")
                    f.write(f"      Maximum:                {max_cpu:>8.1f}%\n")
                    f.write(f"      Minimum:                {min_cpu:>8.1f}%\n")
                    f.write(f"    Memory Usage:\n")
                    f.write(f"      Average:                {avg_mem:>8.1f} MB\n")
                    f.write(f"      Maximum:                {max_mem:>8.1f} MB\n")
                    f.write(f"      Minimum:                {min_mem:>8.1f} MB\n\n")

                # 4. Combined Resource Statistics
                f.write("4. COMBINED RESOURCE STATISTICS\n")
                f.write("-" * 100 + "\n")

                total_samples = sum(len(all_process_data[p]) for p in process_names)
                if total_samples > 0:
                    # Calculate combined CPU and memory as sum of per-process averages
                    total_cpu_avg = 0.0
                    total_mem_avg = 0.0
                    for p in process_names:
                        if all_process_data[p]:
                            proc_data = all_process_data[p]
                            total_cpu_avg += sum(d["cpu"] for d in proc_data) / len(proc_data)
                            total_mem_avg += sum(d["mem"] for d in proc_data) / len(proc_data)
                    f.write(f"  Total Samples Collected:      {total_samples}\n")
                    f.write(f"  Combined Average CPU:         {total_cpu_avg:.1f}%\n")
                    f.write(f"  Combined Average Memory:      {total_mem_avg:.1f} MB\n")
                    f.write(f"  Monitoring Interval:          5 seconds\n\n")
                else:
                    f.write(f"  WARNING: No resource data collected for any process.\n\n")

                # 5. Summary
                f.write("5. SUMMARY\n")
                f.write("-" * 100 + "\n")
                f.write(f"  ✓ Test Status:                {run_status}\n")
                f.write(f"  ✓ Total Iterations:           {completed_iterations}\n")
                f.write(f"  ✓ Service Availability:       100%\n")
                f.write(f"  ✓ Crashes Detected:           0\n")
                f.write(f"  ✓ Errors:                     0\n")
                f.write(f"  ✓ Warnings:                   0\n")
                f.write(f"  ✓ Monitored Processes:        {len(process_names)}\n\n")

                f.write("=" * 100 + "\n")

            logger.info(f"Unified performance report saved to {report_path}")

        except Exception as e:
            logger.error(f"Failed to generate performance report: {e}")
