import threading
import sys
import select
import logging
import time
from interfaces.i_input import IInputMonitor

logger = logging.getLogger()

class LinuxInputMonitor(IInputMonitor):
    """Linux input monitor using select() for keyboard detection."""

    def start_input_monitor(self, stop_event: threading.Event) -> None:
        self.stop_event = stop_event

        def _monitor():
            logger.info("Input monitor started. Press Enter to stop.")
            while not self.stop_event.is_set():
                # Use select to check if input is available on stdin
                dr, dw, de = select.select([sys.stdin], [], [], 0.5)
                if dr:
                    sys.stdin.readline()
                    logger.warning("Key detected. Stopping...")
                    self.stop_event.set()
                time.sleep(0.1)

        th = threading.Thread(target=_monitor, daemon=True)
        th.start()

    def stop_input_monitor(self) -> None:
        """Stop input monitoring."""
        if hasattr(self, 'stop_event') and self.stop_event:
            self.stop_event.set()
