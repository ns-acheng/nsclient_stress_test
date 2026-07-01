import glob
import logging
import os
import shutil
import datetime
import subprocess
import ctypes
from interfaces.i_diag import IDiagnostics

logger = logging.getLogger()

NSDIAG_TIMEOUT_SEC = 300

class WindowsDiagnostics(IDiagnostics):
    def __init__(self):
        self.nsdiag_path = r"C:\Program Files\Netskope\STAgent\nsdiag.exe"
        self.nsdiag_path_x86 = r"C:\Program Files (x86)\Netskope\STAgent\nsdiag.exe"

    def _get_dump_paths(self, custom_dump_path: str = "") -> list[str]:
        paths = [
            r"C:\dump\stAgentSvc.exe\*.dmp",
            r"C:\ProgramData\netskope\stagent\logs\*.dmp"
        ]
        appdata = os.getenv('APPDATA')
        if appdata:
            paths.append(os.path.join(appdata, r"Netskope\stagent\Logs\*.dmp"))
        if custom_dump_path:
            paths.append(custom_dump_path)
        return paths

    def check_crash_dumps(self, custom_dump_path: str = "") -> tuple[bool, int]:
        dump_paths = self._get_dump_paths(custom_dump_path)
        found = False
        zero_count = 0
        for path in dump_paths:
            files = glob.glob(path)
            for f in files:
                try:
                    size = os.path.getsize(f)
                    if size == 0:
                        try:
                            os.remove(f)
                            zero_count += 1
                        except OSError: pass
                        continue
                    logger.error(f"CRASH DUMP DETECTED: {f} (Size: {size})")
                    found = True
                except Exception as e:
                    logger.error(f"Error checking file {f}: {e}")
        return found, zero_count

    def _get_nsdiag_path(self, is_64bit: bool) -> str:
        if is_64bit:
            return self.nsdiag_path
        else:
            return self.nsdiag_path_x86

    def _run_nsdiag(self, nsdiag_path: str, args: list, desc: str) -> bool:
        if not os.path.exists(nsdiag_path):
            logger.error(f"nsdiag.exe not found at: {nsdiag_path}")
            return False
        command = [nsdiag_path] + args
        try:
            logger.info(f"Running nsdiag {desc}: {' '.join(command)}")
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=NSDIAG_TIMEOUT_SEC,
            )
            if result.stdout.strip():
                logger.info(result.stdout.strip())
            if result.stderr.strip():
                logger.warning(result.stderr.strip())
            logger.info(f"nsdiag {desc} executed successfully.")
            return True
        except subprocess.TimeoutExpired:
            logger.error(
                f"nsdiag {desc} timed out after {NSDIAG_TIMEOUT_SEC}s."
            )
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"nsdiag {desc} failed. RC: {e.returncode}")
            return False

    def _export_event_log(self, log_name: str, timestamp: str, output_dir: str) -> bool:
        output_file = os.path.join(output_dir, f"{timestamp}_event_{log_name}.evtx")
        cmd = ["wevtutil", "epl", log_name, output_file, "/ow:true"]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Windows Event Log exported: {output_file}")
            return True
        except FileNotFoundError:
            logger.error("wevtutil not found. Cannot export Windows Event Logs.")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to export Event Log '{log_name}'. RC: {e.returncode}")
            return False
        except Exception as e:
            logger.error(f"Error exporting Event Log '{log_name}': {e}")
            return False

    def _collect_windows_event_logs(self, timestamp: str, output_dir: str) -> None:
        for log_name in ["System", "Application"]:
            self._export_event_log(log_name, timestamp, output_dir)

    def collect_log_bundle(self, timestamp: str, is_64bit: bool, output_dir: str) -> None:
        nsdiag_path = self._get_nsdiag_path(is_64bit)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = os.path.join(output_dir, f"{timestamp}_log_bundle.zip")
        success = self._run_nsdiag(nsdiag_path, ["-o", output_file], "log collection")
        if success:
            logger.info(f"Log bundle created: {output_file}")
        self._collect_windows_event_logs(timestamp, output_dir)

    def sync_client_config(self, is_64bit: bool) -> None:
        nsdiag_path = self._get_nsdiag_path(is_64bit)
        self._run_nsdiag(nsdiag_path, ["-u"], "config update")

    def enable_client_tracing(self, enable: bool, is_64bit: bool) -> None:
        nsdiag_path = self._get_nsdiag_path(is_64bit)
        action = "enable" if enable else "disable"
        self._run_nsdiag(nsdiag_path, ["-t", action], f"client {action}")

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

    def generate_live_dump(self, pid: int, output_dir: str):
        if not os.path.exists(output_dir): os.makedirs(output_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dump_file = os.path.join(output_dir, f"LiveDump_{pid}_{timestamp}.dmp")
        logger.info(f"Generating live dump for PID {pid} -> {dump_file}")
        
        # MiniDump flags
        dump_flags = 0x00000002 | 0x00000004 | 0x00000020 | 0x00000800 | 0x00001000
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        GENERIC_WRITE = 0x40000000
        CREATE_ALWAYS = 2
        FILE_ATTRIBUTE_NORMAL = 0x80

        h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h_process:
            logger.error(f"Failed to OpenProcess {pid}.")
            return

        try:
            h_file = ctypes.windll.kernel32.CreateFileW(dump_file, GENERIC_WRITE, 0, None, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, None)
            if h_file == -1 or h_file == 0xFFFFFFFFFFFFFFFF:
                logger.error(f"Failed CreateFile {dump_file}.")
                return
            try:
                dbghelp = ctypes.windll.LoadLibrary("dbghelp.dll")
                success = dbghelp.MiniDumpWriteDump(h_process, pid, h_file, dump_flags, None, None, None)
                if success:
                    logger.info("Live dump generated successfully.")
                else:
                    logger.error("MiniDumpWriteDump failed.")
            finally:
                ctypes.windll.kernel32.CloseHandle(h_file)
        finally:
            ctypes.windll.kernel32.CloseHandle(h_process)
