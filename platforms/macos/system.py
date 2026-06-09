import os
import subprocess
import logging
import time
import psutil
from datetime import datetime
from interfaces.i_system import ISystemInfo

logger = logging.getLogger()

class MacOSSystemInfo(ISystemInfo):
    def get_process_pid(self, process_name: str) -> int:
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                # MacOS process names might be just the binary name
                if proc.info['name'] == process_name:
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return 0

    def get_memory_usage(self) -> tuple[int, int]:
        # vm_stat can give pages, but it's complex.
        # Use psutil as it is a dependency now.
        try:
            mem = psutil.virtual_memory()
            return (int(mem.percent), int(mem.available / (1024*1024)))
        except Exception:
            return (0, 0) # Stub

    def enable_privilege(self, privilege_name: str) -> int:
        if os.geteuid() != 0:
            logger.warning("Not running as root! Some functions may fail.")
            return 1
        return 0

    def log_process_usage(self, process_name: str, log_dir: str) -> bool:
        # Use ps -p <pid> -o %cpu,%mem whatever
        pid = self._get_pid(process_name)
        if not pid: return False
        
        cmd = ["ps", "-p", str(pid), "-o", "%cpu,rss"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            lines = res.stdout.strip().splitlines()
            if len(lines) > 1:
                vals = lines[1].strip().split()
                if len(vals) >= 2:
                    cpu = float(vals[0])
                    rss_kb = int(vals[1])
                    rss_mb = rss_kb / 1024
                    
                    if not os.path.exists(log_dir): os.makedirs(log_dir)
                    full_path = os.path.join(log_dir, f"{process_name}_resources.log")
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    with open(full_path, "a", encoding='utf-8') as f:
                        f.write(f"{now_str}, {cpu:.1f}%, {rss_mb:.1f}MB, {rss_kb}KB, 0\n")
                    return True
        except Exception as e:
            pass
        return False
        
    def _get_pid(self, name: str) -> int:
        try:
            res = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True)
            if res.stdout.strip():
                return int(res.stdout.splitlines()[0])
        except:
            pass
        return 0

    def set_startup_task(self, task_name: str, command: str) -> bool:
        # Create a LaunchDaemon plist
        plist_path = f"/Library/LaunchDaemons/{task_name}.plist"
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{task_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>{command}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
        try:
            with open(plist_path, "w") as f:
                f.write(plist_content)
            # Load it
            subprocess.run(["sudo", "launchctl", "load", plist_path], check=True)
            logger.info(f"Created LaunchDaemon: {plist_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create startup task: {e}")
            return False

    def remove_startup_task(self, task_name: str) -> None:
        plist_path = f"/Library/LaunchDaemons/{task_name}.plist"
        if os.path.exists(plist_path):
            subprocess.run(["sudo", "launchctl", "unload", plist_path], stderr=subprocess.DEVNULL)
            os.remove(plist_path)

    def run_shell_script(self, script_path: str, args: list = None) -> None:
        cmd = ["/bin/bash", script_path]
        if args: cmd.extend(args)
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
