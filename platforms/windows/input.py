import threading
import time
import msvcrt
import logging
from interfaces.i_input import IInputMonitor

logger = logging.getLogger()

class WindowsInputMonitor(IInputMonitor):
    def start_input_monitor(self, stop_event: threading.Event) -> None:
        self.stop_event = stop_event

        def _monitor():
            logger.info("Input monitor started. Press ESC or Ctrl+C to stop.")
            while not self.stop_event.is_set():
                if msvcrt.kbhit():
                    try:
                        key = msvcrt.getch()
                        if key == b'\x1b' or key == b'\x03':
                            logger.warning("Stop signal detected. Stopping...")
                            self.stop_event.set()
                            break
                    except Exception:
                        pass
                time.sleep(0.1)

        th = threading.Thread(target=_monitor, daemon=True)
        th.start()

    def stop_input_monitor(self) -> None:
        """Stop input monitoring."""
        if hasattr(self, 'stop_event') and self.stop_event:
            self.stop_event.set()
