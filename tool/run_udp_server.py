import argparse
import socket
import logging
import os
import sys
import threading
import time

# Add parent directory to path to import util modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from util_input import start_input_monitor
except ImportError:
    # Fallback if util_input is not available or path is wrong
    def start_input_monitor(stop_event):
        print("Input monitor not available (util_input not found). usage Ctrl+C to stop.")
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("UDP_Server")

def udp_server(port, stop_event, verbose, expect_count=0, stats_interval=5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    server_address = ('0.0.0.0', port)
    
    try:
        sock.bind(server_address)
        sock.settimeout(1.0)
        logger.info(f"UDP Server listening on port {port}")
    except Exception as e:
        logger.error(f"Failed to bind to port {port}: {e}")
        stop_event.set()
        return

    packet_count = 0
    last_log_time = time.time()
    total_bytes = 0
    first_packet_time = None
    threshold_logged = False

    while not stop_event.is_set():
        try:
            data, address = sock.recvfrom(65535)
            now = time.time()
            if first_packet_time is None:
                first_packet_time = now

            packet_count += 1
            total_bytes += len(data)

            if verbose:
                logger.info(
                    f"Received packet #{packet_count}: {len(data)} bytes "
                    f"from {address}"
                )
            else:
                if now - last_log_time >= stats_interval:
                    logger.info(
                        "Stats: "
                        f"received={packet_count} packets, "
                        f"bytes={total_bytes}"
                    )
                    last_log_time = now

            if expect_count > 0 and not threshold_logged and packet_count >= expect_count:
                logger.info(
                    f"Expected packet threshold reached: {packet_count}/{expect_count}"
                )
                threshold_logged = True

        except socket.timeout:
            continue
        except Exception as e:
            logger.error(f"Error receiving data: {e}")
            if getattr(e, 'errno', 0) in [10004, 9]:
                break

    elapsed = 0.0
    if first_packet_time is not None:
        elapsed = max(0.0, time.time() - first_packet_time)

    avg_pps = (packet_count / elapsed) if elapsed > 0 else 0.0
    logger.info(
        "UDP Server summary: "
        f"received={packet_count} packets, "
        f"bytes={total_bytes}, elapsed={elapsed:.2f}s, avg_pps={avg_pps:.2f}"
    )
    if expect_count > 0:
        if packet_count >= expect_count:
            logger.info(
                f"Receive check PASSED: expected={expect_count}, got={packet_count}"
            )
        else:
            logger.warning(
                f"Receive check FAILED: expected={expect_count}, got={packet_count}"
            )

    sock.close()
    logger.info("UDP socket closed")

def main():
    parser = argparse.ArgumentParser(description="Run a simple UDP server/sink.")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging (print every packet)"
    )
    parser.add_argument(
        "--expect-count",
        type=int,
        default=0,
        help="Expected packet count for receive check"
    )
    parser.add_argument(
        "--stats-interval",
        type=float,
        default=5.0,
        help="Periodic stats interval in seconds"
    )
    
    args = parser.parse_args()

    logger.info(f"Starting UDP Server on port {args.port}")
    logger.info("Press ESC to stop the server (or Ctrl+C)")

    stop_event = threading.Event()
    
    # Start input monitor for ESC key
    try:
        start_input_monitor(stop_event)
    except Exception as e:
        logger.warning(f"Could not start input monitor: {e}")

    server_thread = threading.Thread(
        target=udp_server,
        args=(
            args.port,
            stop_event,
            args.verbose,
            args.expect_count,
            args.stats_interval,
        )
    )
    server_thread.daemon = True
    server_thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
        stop_event.set()
    finally:
        logger.info("Stopping UDP server...")
        stop_event.set()
        server_thread.join(timeout=2)
        logger.info("Exited.")

if __name__ == "__main__":
    main()
