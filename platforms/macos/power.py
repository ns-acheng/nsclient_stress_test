import subprocess
import logging
import time
import datetime
from interfaces.i_power import IPowerManager

logger = logging.getLogger()

class MacOSPowerManager(IPowerManager):
    def _schedule_wake(self, duration_seconds: int) -> bool:
        # Schedule a wake event relative to now
        # specific format required: "MM/dd/yyyy HH:mm:ss"
        wake_time = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
        time_str = wake_time.strftime("%m/%d/%Y %H:%M:%S")
        
        # pmset schedule wake "MM/dd/yyyy HH:mm:ss"
        try:
            cmd = ["pmset", "schedule", "wake", time_str]
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Scheduled wake at {time_str}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to schedule wake: {e}")
            return False

    def enter_s0_and_wake(self, duration_seconds: int) -> bool:
        # Map S0 to Display Sleep on Mac
        logger.info(f"Enter Display Sleep for {duration_seconds}s...")
        try:
            subprocess.run(["pmset", "displaysleepnow"], check=True)
            time.sleep(duration_seconds)
            # Wake display is usually done by activity, we can simulate a keypress via AppleScript or caffeinate
            # Using caffeinate -u to simulate user activity to wake display
            subprocess.run(["caffeinate", "-u", "-t", "1"], check=True)
            logger.info("Woke Display.")
            return True
        except Exception as e:
            logger.error(f"Failed to cycle display sleep: {e}")
            return False

    def enter_s1_and_wake(self, duration_seconds: int) -> bool:
        # Map S1 to standard System Sleep
        if not self._schedule_wake(duration_seconds):
            logger.warning("Could not schedule wake, sleep might be indefinite!")
            return False
            
        logger.info(f"Enter System Sleep for {duration_seconds}s...")
        try:
            # pmset sleepnow puts Mac to sleep immediately
            subprocess.run(["pmset", "sleepnow"], check=True)
            # We wait here, mostly the script pauses until wake
            # Add buffer for wake up
            time.sleep(duration_seconds + 5) 
            logger.info("System Woke.")
            return True
        except Exception as e:
            logger.error(f"Failed to enter sleep: {e}")
            return False

    def enter_s4_and_wake(self, duration_seconds: int) -> bool:
        # MacOS doesn't distinguish Hibernate (S4) vs Sleep (S3) easily via command 
        # without changing pmset mode globally. We will map to same sleep logic.
        logger.info("Mapping S4 to System Sleep on MacOS.")
        return self.enter_s1_and_wake(duration_seconds)

    def is_sleep_state_available(self, state_name: str) -> bool:
        # On MacOS, basic sleep is always available usually.
        # We can run `pmset -g cap` to see capabilities.
        try:
            res = subprocess.run(["pmset", "-g", "cap"], capture_output=True, text=True)
            if "Sleep" in res.stdout:
                return True
        except:
            pass
        return False

    def reboot(self) -> None:
        logger.info("Triggering System Reboot Now!")
        try:
            subprocess.run(["sudo", "shutdown", "-r", "now"], check=False)
        except Exception as e:
            logger.error(f"Failed to trigger reboot: {e}")

    def enable_wake_timers(self) -> bool:
        # Not strictly applicable like Windows, but we can ensure everything is right
        return True
