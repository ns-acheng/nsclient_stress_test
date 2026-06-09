import threading
import time
import sys
import logging

logger = logging.getLogger()

def start_input_monitor(stop_event: threading.Event) -> None:
    if sys.platform == 'win32':
        _start_windows_monitor(stop_event)
    else:
        _start_unix_monitor(stop_event)

def _start_windows_monitor(stop_event):
    import msvcrt
    def _monitor():
        logger.info("Input monitor started. Press ESC to stop.")
        while not stop_event.is_set():
            if msvcrt.kbhit():
                try:
                    key = msvcrt.getch()
                    if key == b'\x1b':
                        logger.warning("Stop signal detected. Stopping...")
                        stop_event.set()
                        break
                except Exception:
                    pass
            time.sleep(0.1)
    
    t = threading.Thread(target=_monitor, daemon=True)
    t.start()

def _start_unix_monitor(stop_event):
    import select
    def _monitor():
        logger.info("Input monitor started. Press Enter to stop.")
        while not stop_event.is_set():
            dr, dw, de = select.select([sys.stdin], [], [], 0.5)
            if dr:
                sys.stdin.readline()
                logger.warning("Key detected. Stopping...")
                stop_event.set()
            time.sleep(0.1)

    t = threading.Thread(target=_monitor, daemon=True)
    t.start()
