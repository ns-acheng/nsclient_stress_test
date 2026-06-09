import random
import logging
from util_time import smart_sleep

logger = logging.getLogger()

def _wait_interval(duration, stop_event) -> bool:
    steps = int(duration // 2)
    remainder = duration % 2
    for _ in range(steps):
        if smart_sleep(2, stop_event): return True
    if remainder > 0:
        if smart_sleep(remainder, stop_event): return True
    return False

def client_toggler_loop(
    stop_event,
    service_name,
    is_64bit,
    enable_min,
    enable_max,
    disable_ratio,
    client_enabled_event=None,
    service_mgr=None,
    diag_mgr=None
) -> None:

    logger.info("Client Toggle Thread Started.")
    disable_count = 0
    while not stop_event.is_set():
        if client_enabled_event:
            client_enabled_event.set()

        run_time = random.randint(enable_min, enable_max)
        logger.info(f"Client Toggle Thread: Keeping enabled for {run_time}s...")
        if _wait_interval(run_time, stop_event): break

        # Check Service Status
        status = "UNKNOWN"
        if service_mgr:
            status = service_mgr.get_service_status(service_name)
        
        if status != "RUNNING":
            logger.info("Client Toggle Thread: Service not running, skip toggle.")
            continue

        disable_time = int(run_time * disable_ratio)
        if disable_time < 1: disable_time = 1

        disable_count += 1
        logger.info(f"Client Toggle Thread: Disabling Client (Time: {disable_count}) for {disable_time}s...")
        
        if diag_mgr:
            diag_mgr.enable_client_tracing(False, is_64bit)
        
        if client_enabled_event:
            client_enabled_event.clear()

        if _wait_interval(disable_time, stop_event): break

        logger.info("Client Toggle Thread: Re-enabling Client...")
        
        if diag_mgr:
            diag_mgr.enable_client_tracing(True, is_64bit)
