import logging
from interfaces.i_power import IPowerManager

logger = logging.getLogger()

class LinuxPowerManager(IPowerManager):
    """
    Linux power management stub implementation.

    Power management features (S0/S1/S4 sleep states) are Windows-specific.
    Linux implementation returns False for all power operations as per CLAUDE.md.
    """

    def enter_s0_and_wake(self, duration_seconds: int) -> bool:
        logger.warning("Power management not supported on Linux platform")
        return False

    def enter_s1_and_wake(self, duration_seconds: int) -> bool:
        logger.warning("Power management not supported on Linux platform")
        return False

    def enter_s4_and_wake(self, duration_seconds: int) -> bool:
        logger.warning("Power management not supported on Linux platform")
        return False

    def is_sleep_state_available(self, state_name: str) -> bool:
        return False

    def reboot(self) -> None:
        logger.info("Triggering system reboot...")
        try:
            import subprocess
            subprocess.run(["sudo", "reboot"], check=False)
        except Exception as e:
            logger.error(f"Failed to trigger reboot: {e}")

    def enable_wake_timers(self) -> bool:
        return False
