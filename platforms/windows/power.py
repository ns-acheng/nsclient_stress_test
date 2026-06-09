import ctypes
from ctypes import wintypes
import logging
import subprocess
import time
import os
from interfaces.i_power import IPowerManager

logger = logging.getLogger()
kernel32 = ctypes.windll.kernel32
user32 = ctypes.windll.user32

HWND_BROADCAST = 0xFFFF
WM_SYSCOMMAND = 0x0112
SC_MONITORPOWER = 0xF170
MONITOR_OFF = 2
MONITOR_ON = -1
KEYEVENTF_KEYUP = 0x0002

class LARGE_INTEGER(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD),
                ("HighPart", wintypes.LONG)]

class WindowsPowerManager(IPowerManager):
    def _powercfg_output(self) -> str:
        cmd = ["cmd", "/c", "chcp 65001 && powercfg /a"]
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace'
            )
            if res.returncode != 0:
                logger.warning(f"powercfg /a returned code {res.returncode}")
            return res.stdout
        except Exception as e:
            logger.error(f"Failed to run powercfg /a: {e}")
            return ""

    def _is_s0_low_power_idle(self) -> bool:
        output = self._powercfg_output()
        markers = ["Standby (S0 Low Power Idle)", "待命 (S0 低電源閒置)"]
        return any(term in output for term in markers)

    def _run_pwrtest(self, args: list) -> bool:
        # tool is located in platforms/windows/tool/pwrtest.exe relative to project,
        # or relative to this file: ./tool/pwrtest.exe
        pwrtest_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "tool", "pwrtest.exe"
        )
        if not os.path.exists(pwrtest_path):
            # Fallback for legacy structure if file not found locally
            pwrtest_path = os.path.join("tool", "pwrtest.exe")
            if not os.path.exists(pwrtest_path):
                return False
        
        cmd = [pwrtest_path] + args
        try:
            full_cmd = ' '.join(cmd)
            logger.info(f"Running PwrTest command: {full_cmd}")
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"PwrTest failed with code {e.returncode}")
            return False
        except Exception as e:
            logger.error(f"PwrTest execution error: {e}")
            return False

    def _set_wake_timer(self, duration_seconds: int) -> int | None:
        handle = kernel32.CreateWaitableTimerW(None, True, None)
        if not handle:
            logger.error(f"Failed create timer. Err: {kernel32.GetLastError()}")
            return None

        dt = int(duration_seconds * 10000000) * -1
        li = LARGE_INTEGER(dt & 0xFFFFFFFF, dt >> 32)

        if not kernel32.SetWaitableTimer(
            handle, ctypes.byref(li), 0, None, None, True
        ):
            logger.error(f"Failed set timer. Err: {kernel32.GetLastError()}")
            kernel32.CloseHandle(handle)
            return None
        return handle

    def enter_s0_and_wake(self, duration_seconds: int) -> bool:
        # PwrTest /cs /c:1 /p:duration /d:0
        if self._run_pwrtest(["/cs", "/c:1", f"/p:{duration_seconds}", "/d:0"]):
            logger.info("PwrTest S0 cycle completed successfully.")
            return True
            
        # Fallback to legacy Monitor OFF method if PwrTest fails/missing
        logger.info("Falling back to legacy S0 (Monitor OFF)...")
        handle = self._set_wake_timer(duration_seconds)
        if not handle:
            return False

        try:
            logger.info(f"Enter S0 (Monitor OFF) for {duration_seconds}s...")
            user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_OFF)
            kernel32.WaitForSingleObject(handle, -1)
            user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, MONITOR_ON)
            
            # Simulate interaction
            user32.keybd_event(0, 0, 0, 0)
            user32.keybd_event(0, 0, KEYEVENTF_KEYUP, 0)
            
            logger.info("System Woke (Monitor ON).")
            return True
        except Exception as e:
            logger.error(f"Failed to cycle S0: {e}")
            return False
        finally:
            kernel32.CloseHandle(handle)

    def enter_s1_and_wake(self, duration_seconds: int) -> bool:
        if self._run_pwrtest(["/sleep", "/s:1", "/c:1", f"/p:{duration_seconds}", "/d:0"]):
            logger.info("PwrTest S1 cycle completed successfully.")
            return True

        logger.info("Falling back to legacy Standby (S1)...")
        handle = self._set_wake_timer(duration_seconds)
        if not handle:
            return False
        try:
            logger.info(f"Enter S1 (Standby) for {duration_seconds}s...")
            ctypes.windll.powrprof.SetSuspendState(0, 0, 0)
            kernel32.WaitForSingleObject(handle, -1)
            logger.info("System Woke from S1 (Standby).")
            return True
        except Exception as e:
            logger.error(f"Failed to enter S1: {e}")
            return False
        finally:
            kernel32.CloseHandle(handle)

    def enter_s4_and_wake(self, duration_seconds: int) -> bool:
        if self._is_s0_low_power_idle():
            logger.info("AOAC platform detected. Skip PwrTest S4; using legacy path.")
            return self._enter_s4_legacy(duration_seconds)

        if self._run_pwrtest(["/sleep", "/s:s4", "/dt:60", f"/p:{duration_seconds}"]):
            logger.info("PwrTest S4 cycle completed successfully.")
            return True

        logger.info("PwrTest S4 failed. Using legacy Hibernate (S4)...")
        return self._enter_s4_legacy(duration_seconds)

    def _enter_s4_legacy(self, duration_seconds: int) -> bool:
        handle = self._set_wake_timer(duration_seconds)
        if not handle:
            return False
        try:
            logger.info(f"Enter S4 (Hibernate) for {duration_seconds}s...")
            ctypes.windll.powrprof.SetSuspendState(1, 0, 0)
            kernel32.WaitForSingleObject(handle, -1)
            logger.info("System Woke from S4.")
            return True
        except Exception as e:
            logger.error(f"Failed to enter S4: {e}")
            return False
        finally:
            kernel32.CloseHandle(handle)

    def is_sleep_state_available(self, state_name: str) -> bool:
        try:
            output = self._powercfg_output()
            if not output:
                return False
            available_section = output
            
            not_available_markers = [
                "The following sleep states are not available",
                "此系統缺乏以下幾種睡眠狀態"
            ]
            for marker in not_available_markers:
                if marker in output:
                    available_section = output.split(marker)[0]
                    break

            search_candidates = [state_name]
            if state_name == "Hibernate":
                search_candidates.append("休眠")
            elif state_name == "Standby (S1)":
                search_candidates.append("待命 (S1)")
            elif state_name == "Standby (S0 Low Power Idle)":
                search_candidates.append("待命 (S0 低電源閒置)")

            for term in search_candidates:
                if term in available_section:
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to check {state_name} availability: {e}")
            return False

    def reboot(self) -> None:
        logger.info("Triggering System Reboot Now!")
        try:
            subprocess.run(["shutdown", "/r", "/t", "0"], check=False)
        except Exception as e:
            logger.error(f"Failed to trigger reboot: {e}")

    def enable_wake_timers(self) -> bool:
        subgroup = "238C9FA8-0AAD-41ED-83F4-97BE242C8F20"
        setting  = "BD3B718A-0680-4D9D-8AB2-E1D2B4EF806D"
        val = "1"
        commands = [
            ["powercfg", "/setacvalueindex", "SCHEME_CURRENT", subgroup, setting, val],
            ["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", subgroup, setting, val],
            ["powercfg", "/setactive", "SCHEME_CURRENT"]
        ]
        try:
            logger.info("Enabling 'Allow wake timers' in Power Settings...")
            for cmd in commands:
                subprocess.run(
                    cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            return True
        except subprocess.CalledProcessError:
            logger.warning("Failed to enable wake timers.")
            return False
