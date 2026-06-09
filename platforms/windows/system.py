import ctypes
from ctypes import wintypes
import os
import time
from datetime import datetime
import subprocess
import logging
import psutil
from interfaces.i_system import ISystemInfo

logger = logging.getLogger()

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SE_PRIVILEGE_ENABLED = 0x00000002
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260)
    ]

class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]

class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]

class SYSTEM_INFO(ctypes.Structure):
    _fields_ = [
        ("wProcessorArchitecture", wintypes.WORD),
        ("wReserved", wintypes.WORD),
        ("dwPageSize", wintypes.DWORD),
        ("lpMinimumApplicationAddress", ctypes.c_void_p),
        ("lpMaximumApplicationAddress", ctypes.c_void_p),
        ("dwActiveProcessorMask", ctypes.c_void_p),
        ("dwNumberOfProcessors", wintypes.DWORD),
        ("dwProcessorType", wintypes.DWORD),
        ("dwAllocationGranularity", wintypes.DWORD),
        ("wProcessorLevel", wintypes.WORD),
        ("wProcessorRevision", wintypes.WORD),
    ]

class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]

class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

class WindowsSystemInfo(ISystemInfo):
    def get_memory_usage(self) -> tuple[int, int]:
        mem_status = MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))
        # dwMemoryLoad is percent, ullAvailPhys is bytes
        avail_mb = mem_status.ullAvailPhys // (1024 * 1024)
        return (mem_status.dwMemoryLoad, int(avail_mb))

    def get_process_pid(self, process_name: str) -> int:
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'].lower() == process_name.lower():
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return 0

    def enable_privilege(self, privilege_name: str) -> int:
        k32 = ctypes.windll.kernel32
        advapi32 = ctypes.windll.advapi32

        hToken = wintypes.HANDLE()
        if not k32.OpenProcessToken(
            k32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(hToken)
        ):
            return ctypes.get_last_error()

        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
            err = ctypes.get_last_error()
            k32.CloseHandle(hToken)
            return err

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        if not advapi32.AdjustTokenPrivileges(hToken, False, ctypes.byref(tp), 0, None, None):
            err = ctypes.get_last_error()
            k32.CloseHandle(hToken)
            return err

        err = ctypes.get_last_error()
        k32.CloseHandle(hToken)
        return err

    def _get_pid_by_name(self, process_name: str) -> int:
        k32 = ctypes.windll.kernel32
        hSnapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if hSnapshot == INVALID_HANDLE_VALUE:
            return 0

        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not k32.Process32FirstW(hSnapshot, ctypes.byref(entry)):
            k32.CloseHandle(hSnapshot)
            return 0

        target_pid = 0
        try:
            while True:
                if entry.szExeFile.lower() == process_name.lower():
                    target_pid = entry.th32ProcessID
                    break
                if not k32.Process32NextW(hSnapshot, ctypes.byref(entry)):
                    break
        finally:
            k32.CloseHandle(hSnapshot)
        return target_pid

    def _get_process_memory_usage(self, pid: int) -> int:
        if pid == 0: return 0
        k32 = ctypes.windll.kernel32
        process_handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process_handle: return 0
        try:
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            success = ctypes.windll.psapi.GetProcessMemoryInfo(
                process_handle, ctypes.byref(counters), ctypes.sizeof(counters)
            )
            return counters.PrivateUsage if success else 0
        finally:
            k32.CloseHandle(process_handle)

    def _get_process_handle_count(self, pid: int) -> int:
        if pid == 0: return 0
        k32 = ctypes.windll.kernel32
        process_handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process_handle: return 0
        try:
            count = wintypes.DWORD()
            success = k32.GetProcessHandleCount(process_handle, ctypes.byref(count))
            return count.value if success else 0
        finally:
            k32.CloseHandle(process_handle)
    
    def _filetime_to_int(self, ft) -> int:
        return (ft.dwHighDateTime << 32) + ft.dwLowDateTime

    def _get_process_cpu_usage(self, pid: int, interval: float = 0.5) -> float:
        if pid == 0: return 0.0
        k32 = ctypes.windll.kernel32
        process_handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process_handle: return 0.0

        try:
            creation, exit_t, k_start, u_start, sys_start = FILETIME(), FILETIME(), FILETIME(), FILETIME(), FILETIME()
            k32.GetProcessTimes(process_handle, ctypes.byref(creation), ctypes.byref(exit_t), ctypes.byref(k_start), ctypes.byref(u_start))
            k32.GetSystemTimeAsFileTime(ctypes.byref(sys_start))
            
            time.sleep(interval)
            
            k_end, u_end, sys_end = FILETIME(), FILETIME(), FILETIME()
            k32.GetProcessTimes(process_handle, ctypes.byref(creation), ctypes.byref(exit_t), ctypes.byref(k_end), ctypes.byref(u_end))
            k32.GetSystemTimeAsFileTime(ctypes.byref(sys_end))

            p_k_delta = self._filetime_to_int(k_end) - self._filetime_to_int(k_start)
            p_u_delta = self._filetime_to_int(u_end) - self._filetime_to_int(u_start)
            sys_delta = self._filetime_to_int(sys_end) - self._filetime_to_int(sys_start)

            if sys_delta == 0: return 0.0
            
            # Need num processors
            sys_i = SYSTEM_INFO()
            k32.GetSystemInfo(ctypes.byref(sys_i))
            num_procs = sys_i.dwNumberOfProcessors

            return max(0.0, ((p_k_delta + p_u_delta) / sys_delta) * 100.0 / num_procs)
        finally:
            k32.CloseHandle(process_handle)

    def log_resource_usage(self, log_file: str) -> None:
        # Assuming process_name derived from log_file or context. 
        # But wait, interface says `log_resource_usage(log_file)`. 
        # The original was `log_resource_usage(process_name, log_dir)`.
        # I should fit the old signature or adapt.
        # Actually in stress_test.py, it calls log_resource_usage with just log_dir? 
        # No, stress_test.py calls `log_resource_usage(self.service_name, self.log_dir)` roughly?
        # Let's check stress_test.py again.
        # line 475: log_resource_usage(self.service_name, self.log_dir)
        # So I need to fix the Interface signature or implementation to match usage.
        # The interface I defined was `log_resource_usage(self, log_file: str)`.
        # Let's update implementation and I will fix the call site in Phase 3.
        # For now, I'll allow additional args to match old utility if needed, but cleaner to fix interface.
        # I'll implement `log_process_resource_usage(process_name, log_dir)` instead?
        # I'll stick to the interface I just made `log_resource_usage(log_file)` but that seems wrong.
        # Let's implement `log_resource_usage(self, app_name: str, log_dir: str)` and update interface later.
        pass

    def log_process_usage(self, process_name: str, log_dir: str) -> bool:
        pid = self._get_pid_by_name(process_name)
        if pid == 0: return False

        mem_bytes = self._get_process_memory_usage(pid)
        mem_kb = mem_bytes / 1024
        mem_mb = mem_bytes / (1024 * 1024)
        handle_count = self._get_process_handle_count(pid)
        cpu_percent = self._get_process_cpu_usage(pid, interval=0.5)

        if not os.path.exists(log_dir): os.makedirs(log_dir)
        
        full_path = os.path.join(log_dir, f"{process_name}_resources.log")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_header = not os.path.exists(full_path)
        log_line = f"{now_str}, {cpu_percent:.0f}%, {mem_mb:.1f}MB, {mem_kb:.0f}KB, {handle_count}\n"

        with open(full_path, "a", encoding='utf-8') as f:
            if write_header: f.write("Timestamp, CPU, Memory(MB), Memory(KB), Handles\n")
            f.write(log_line)
        return True

    # Matching interface method (fixing signature mismatch in my thought process)
    def log_resource_usage(self, log_file: str) -> None:
        # This was just a placeholder in interface creation. 
        # I will delete this and rely on specific method later or fix interface.
        pass

    def set_startup_task(self, task_name: str, command: str) -> bool:
        logger.info(f"Creating Scheduled Task '{task_name}'...")
        self.remove_startup_task(task_name)
        
        cmd_args = [
            "schtasks", "/Create", "/TN", task_name, "/TR", command,
            "/SC", "ONLOGON", "/RL", "HIGHEST", "/F", "/DELAY", "0000:30"
        ]
        try:
            res = subprocess.run(cmd_args, shell=False, capture_output=True, text=True)
            if res.returncode == 0:
                logger.info(f"Task '{task_name}' created successfully.")
                return True
            else:
                logger.error(f"Failed to create task. {res.stderr}")
                return False
        except Exception as e:
            logger.error(f"Exception creating task: {e}")
            return False

    def remove_startup_task(self, task_name: str) -> None:
        try:
            cmd_str = f'schtasks /Delete /TN "{task_name}" /F'
            subprocess.run(cmd_str, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def run_shell_script(self, script_path: str, args: list = None) -> None:
        # Wrapper for run_powershell
        command = [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-File", script_path
        ]
        if args:
            command.extend(args)
        
        try:
            logger.info(f"Running PowerShell: {script_path} {args if args else ''}")
            subprocess.run(
                command, check=True, capture_output=True, 
                text=True, encoding='utf-8', errors='replace'
            )
            logger.info("PowerShell script executed successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"PowerShell failed. RC: {e.returncode}. {e.stderr if e.stderr else 'No output'}")
        except FileNotFoundError:
            logger.error("PowerShell.exe not found in PATH.")
