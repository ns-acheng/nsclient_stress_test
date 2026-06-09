import socket
import random
import shutil
import string
import sys
import time
import concurrent.futures
import subprocess
import os
import logging
import threading
import requests
import ftplib
import io
import paramiko
import itertools
import psutil

def run_batch(batch_file: str) -> None:
    # Run and wait for completion to ensure browsers are fully opened before continuing
    try:
        subprocess.run(batch_file, shell=True, check=False)
    except Exception as e:
        logger.error(f"Failed to run batch file {batch_file}: {e}")

def run_curl(url: str) -> None:
    try:
        subprocess.Popen(
            ["curl", "-k", "-v", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False 
        )
    except Exception:
        pass

def get_system_memory_usage() -> float:
    try:
        return psutil.virtual_memory().percent / 100.0
    except:
        return 0.0

def log_resource_usage(process_name, log_dir):
    try:
        found = False
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
            if proc.info['name'] == process_name:
                found = True
                cpu = proc.info['cpu_percent']
                mem = proc.info['memory_info'].rss / (1024 * 1024)
                # Matches format expected? "DATE, CPU%, RSS_MB, RSS_KB, 0"
                # This logic duplicates what's in ISystemInfo. But util_traffic doesn't have access to ISystemInfo efficiently without passing it down deep.
                # For now, let's just log it if we can, or skip it.
                # The old utili_resources used 'log_resource_usage' which appended to a file.
                pass 
                # Doing file I/O here properly matches the old behavior?
                # The old behavior wrote to "log_dir/process_name_resources.log"
                if not os.path.exists(log_dir): os.makedirs(log_dir)
                full_path = os.path.join(log_dir, f"{process_name}_resources.log")
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                with open(full_path, "a", encoding='utf-8') as f:
                     f.write(f"{now_str}, {cpu:.1f}%, {mem:.1f}MB, 0KB, 0\n")
        
    except:
        pass

from util_time import smart_sleep

logger = logging.getLogger()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
}

def _is_stopped(stop_event) -> bool:
    if stop_event is None:
        return False
    return stop_event.is_set()

def read_urls_from_file(filename) -> list[str] | None:
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    urls.append(line.strip())
        return urls
    except FileNotFoundError:
        logger.error(f"Error: The file '{filename}' was not found.")
        return None

def check_url_alive(url) -> str:
    try:
        response = requests.head(
            url, timeout=5, allow_redirects=True, headers=headers
        )
        if response.status_code < 400 or response.status_code == 403:
            if response.url != url:
                logger.info(f"Redirect detected: {url} -> {response.url}")

            return response.url
        return ""
    except Exception:
        return ""

def check_urls_and_write_status(urls) -> None:
    if not urls:
        return

    existing_urls = set()
    target_check_file = os.path.join("data", "url.txt")

    if os.path.exists(target_check_file):
        try:
            with open(target_check_file, 'r', encoding='utf-8') as f:
                existing_urls = {line.strip() for line in f if line.strip()}
        except FileNotFoundError:
            pass

    out_file = r'data\url_alive.txt'
    flush_interval = 50
    alive_count = 0
    written_urls = set()

    with open(out_file, 'w', encoding='utf-8') as f:
        for index, url in enumerate(urls):
            if url in existing_urls:
                continue

            alive_url = check_url_alive(url)
            is_alive = bool(alive_url)
            final_url = alive_url if is_alive else url
            status_text = "ALIVE" if is_alive else "DEAD"

            logger.info(f"[{index + 1}/{len(urls)}] {url} -> {status_text}")

            if is_alive:
                if final_url in existing_urls:
                    logger.info(f"Skipping duplicate final URL (in DB): {final_url}")
                    continue
                if final_url in written_urls:
                    logger.info(f"Skipping duplicate final URL (already written): {final_url}")
                    continue

                f.write(f"{final_url}\n")
                written_urls.add(final_url)
                alive_count += 1
                if (index + 1) % flush_interval == 0:
                    f.flush()

    logger.info(f"Complete. Wrote {alive_count} ALIVE URLs to '{out_file}'.")

def _dns_worker(domain) -> None:
    try:
        chars = string.ascii_lowercase + string.digits
        rand_sub = ''.join(random.choices(chars, k=8))
        target = f"{rand_sub}.{domain}"
        socket.gethostbyname(target)
    except Exception:
        pass

def generate_dns_flood(
    domains: list,
    count: int,
    duration: float = 0,
    concurrency: int = 20,
    stop_event: threading.Event = None
) -> None:
    if not domains:
        return

    msg = f"DNS flood: {count} queries"
    if duration > 0:
        msg += f", duration {duration}s"
    msg += f", {concurrency} workers"
    logger.info(msg)

    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0

    completed = 0
    milestone = max(1, int(count * 0.2)) if count > 0 else 100

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
        futures = []

        def submit_batch(n):
            for _ in range(n):
                dom = random.choice(domains)
                futures.append(exe.submit(_dns_worker, dom))

        if duration > 0:
            pass
        else:
            submit_batch(count)

        if duration > 0:
            def _time_worker():
                while time.time() < end_time:
                    if _is_stopped(stop_event): break
                    _dns_worker(random.choice(domains))

            futures = []
            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))

            concurrent.futures.wait(futures)

        else:
            for _ in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                completed += 1
                if count > 0 and completed % milestone == 0:
                    pct = int((completed / count) * 100)
                    logger.info(f"DNS Flood progress: {pct}%")

def _udp_worker(
    target,
    port,
    duration,
    count,
    stop_event,
    family,
    stats: dict | None = None
) -> None:
    sock = socket.socket(family, socket.SOCK_DGRAM)
    payload = os.urandom(1024)

    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0

    sent = 0
    send_failures = 0
    try:
        while True:
            if _is_stopped(stop_event):
                break

            if duration > 0:
                if time.time() >= end_time:
                    break
            elif count > 0:
                if sent >= count:
                    break
            else:
                if sent >= 1:
                    break

            try:
                sock.sendto(payload, (target, port))
                sent += 1
            except Exception:
                send_failures += 1
    except Exception:
        pass
    finally:
        if stats is not None:
            stats["sent"] = sent
            stats["send_failures"] = send_failures
        sock.close()

def generate_udp_flood(
    target: str,
    port: int,
    count: int = 0,
    duration: float = 0,
    concurrency: int = 1,
    stop_event: threading.Event = None,
    ipv6: bool = False
) -> None:
    concurrency = max(1, concurrency)

    msg = f"UDP flood -> {target}:{port}"
    if duration > 0:
        msg += f" for {duration}s"
    if count > 0:
        msg += f", limit {count} pkts"
    msg += f", {concurrency} threads (IPv6={ipv6})"
    logger.info(msg)

    family = socket.AF_INET6 if ipv6 else socket.AF_INET

    threads = []
    worker_stats: list[dict] = []

    base_count_per_thread = count // concurrency if count > 0 else 0
    remainder = count % concurrency if count > 0 else 0

    for i in range(concurrency):
        thread_count = 0
        if count > 0:
            thread_count = base_count_per_thread + (1 if i < remainder else 0)

        stats = {"sent": 0, "send_failures": 0}
        worker_stats.append(stats)

        t = threading.Thread(
            target=_udp_worker,
            args=(
                target,
                port,
                duration,
                thread_count,
                stop_event,
                family,
                stats,
            )
        )
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    total_sent = sum(s.get("sent", 0) for s in worker_stats)
    total_send_failures = sum(s.get("send_failures", 0) for s in worker_stats)

    summary = (
        "UDP Flood finished. "
        f"sent={total_sent}, send_failures={total_send_failures}, "
        f"threads={concurrency}"
    )
    if count > 0:
        summary += f", planned={count}"
    logger.info(summary)

    if count > 0 and total_sent < count:
        logger.warning(
            f"UDP Flood short send detected: planned={count}, sent={total_sent}"
        )

def run_high_concurrency_test(
    target_url: str,
    requests: int,
    concurrency: int,
    tool_dir: str,
    stop_event: threading.Event = None,
    duration: float = 0
) -> None:
    # Determine AB path based on platform
    if sys.platform.startswith('win'):
        ab_path = os.path.join(tool_dir, "ab", "ab.exe")
        if not os.path.exists(ab_path):
            logger.warning(f"AB not found at {ab_path}. Skipping.")
            return
    else:
        # On macOS/Linux, try system ab
        ab_paths = ["/usr/sbin/ab", "/usr/bin/ab"]
        ab_path = None
        
        # First check absolute paths
        for path in ab_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ab_path = path
                break
        
        # If not found, check PATH
        if not ab_path:
            ab_path = shutil.which("ab")

        if not ab_path:
            logger.warning("Apache Benchmark (ab) not found in system. Skipping.")
            return

    if duration > 0:
        logger.info(
            f"Run AB: {concurrency} conn -> {target_url} for {duration}s"
        )
        cmd = [
            ab_path, "-t", str(int(duration)),
            "-n", "2000000000",
            "-c", str(concurrency), "-k", target_url
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                errors='replace'
            )

            start_time = time.time()
            next_pct = 20

            timeout = duration * 2
            while proc.poll() is None:
                if _is_stopped(stop_event):
                    logger.warning("Stop signal received. Killing AB...")
                    proc.kill()
                    return

                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(
                        f"AB exceeded timeout ({timeout}s). Killing..."
                    )
                    proc.kill()
                    break

                if (elapsed / duration) * 100 >= next_pct:
                    logger.info(f"AB Test progress: {next_pct}%")
                    next_pct += 20

                time.sleep(0.5)

            proc.communicate()
            if proc.returncode != 0:
                 logger.error(f"AB failed (RC {proc.returncode})")
            else:
                 logger.info("AB finished successfully.")

        except Exception as e:
            logger.error(f"Failed to run AB: {e}")

    else:
        batches = 5
        if requests < batches:
            batches = 1

        chunk_size = max(1, requests // batches)
        logger.info(
            f"Run AB: {requests} reqs (split {batches}), "
            f"{concurrency} conn -> {target_url}"
        )

        for i in range(batches):
            if _is_stopped(stop_event):
                break

            cmd = [
                ab_path, "-n", str(chunk_size),
                "-c", str(concurrency), "-k", target_url
            ]

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding='utf-8',
                    errors='replace'
                )

                while proc.poll() is None:
                    if _is_stopped(stop_event):
                        logger.warning("Stop signal received. Killing AB...")
                        proc.kill()
                        return
                    time.sleep(0.5)

                proc.communicate()

                if proc.returncode != 0:
                    logger.error(f"AB batch {i+1} failed (RC {proc.returncode})")
                else:
                    pct = int(((i + 1) / batches) * 100)
                    logger.info(f"AB Test progress: {pct}%")

            except Exception as e:
                logger.error(f"Failed to run AB batch {i+1}: {e}")

        logger.info("AB finished successfully.")

def open_browser_tabs(
    urls, tool_dir, max_tabs, max_mem, stop_event, log_dir, wait_sec
) -> list[str]:
    opened_urls = []
    if not urls:
        logger.warning("No URLs loaded to open.")
        return opened_urls

    logger.info(
        f"Start tab loop. Max Mem: {max_mem}%, Max Tabs: {max_tabs}"
    )

    batch_cnt = 0
    total_tabs = 0
    batch_limit = 30

    while batch_cnt < batch_limit:
        if _is_stopped(stop_event):
            break
        if total_tabs >= max_tabs:
            logger.info(f"Max tabs ({total_tabs}). Stop opening.")
            break

        remaining = max_tabs - total_tabs
        count = min(len(urls), 10)
        count = min(count, remaining)

        if count <= 0:
            break

        selected = random.sample(urls, count)
        logger.info(f"Opening batch {batch_cnt + 1} ({len(selected)} URLs)...")
        for u in selected:
            logger.info(f"  -> {u}")

        args = " ".join([f'"{u}"' for u in selected])
        if sys.platform.startswith("win"):
            script_name = "open_msedge_tabs.bat"
        elif sys.platform.startswith("darwin"):
            script_name = "open_msedge_tabs.sh"
        elif sys.platform.startswith("linux"):
            script_name = "open_browsers.sh"
        else:
            script_name = "open_browsers.sh"  # fallback for other Unix-like systems
        bat_path = os.path.join(tool_dir, script_name)
        cmd = f'"{bat_path}" {args}'
        run_batch(cmd)

        opened_urls.extend(selected)

        total_tabs += count
        if smart_sleep(wait_sec, stop_event):
            break
        log_resource_usage("stAgentSvc.exe", log_dir)

        mem = get_system_memory_usage() * 100.0
        logger.info(f"System Mem: {mem:.2f}% (Target: {max_mem}%)")

        if mem >= max_mem:
            logger.info(f"Threshold reached ({mem:.2f}%).")
            break

        batch_cnt += 1

    if batch_cnt >= batch_limit:
        logger.warning(f"Reached max batch limit ({batch_limit})")

    return opened_urls

def curl_requests(urls, stop_event=None) -> None:
    if not urls:
        return

    mandatory = {urls[0], urls[-1]}
    pool = [u for u in urls if u not in mandatory]

    count = min(len(urls), 10)
    needed = count - len(mandatory)

    selected = list(mandatory)
    if needed > 0 and pool:
        selected.extend(random.sample(pool, min(len(pool), needed)))

    logger.info(f"Running CURL on {len(selected)} URLs (incl. first/last)...")

    for url in selected:
        if _is_stopped(stop_event):
            break
        run_curl(url)
        logger.info(f"CURL with URL: {url}")

def _curl_flood_worker(url) -> str:
    try:
        cmd = ["curl", "-k", "-s", "--max-time", "15", "-o", "NUL", url]
        subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass
    return url

def generate_curl_flood(
    urls,
    count,
    duration=0,
    concurrency=50,
    stop_event=None
) -> list[str]:
    all_used_urls = []
    if not urls:
        logger.warning("No URLs for CURL flood.")
        return all_used_urls

    msg = f"Start CURL Flood: {concurrency} workers"
    if duration > 0:
        msg += f", duration {duration}s"
    else:
        msg += f", {count} reqs"
    logger.info(msg)

    if duration > 0:
        end_time = time.time() + duration

        def _time_worker():

            local_pool = list(urls)

            cycler = itertools.cycle(local_pool)

            while time.time() < end_time:
                if _is_stopped(stop_event): break
                url = next(cycler)
                _curl_flood_worker(url)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency
        ) as exe:
            futures = []
            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))
            concurrent.futures.wait(futures)

    else:
        milestone = max(1, int(count * 0.2))
        completed = 0
        log_buffer = []

        pool = list(urls)

        if count > len(pool):
            url_iter = itertools.cycle(pool)
        else:
            url_iter = iter(pool)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=concurrency
        ) as exe:
            futures = []
            for i in range(1, count + 1):
                if _is_stopped(stop_event):
                    break
                try:
                    url = next(url_iter)
                except StopIteration:

                    url_iter = itertools.cycle(pool)
                    url = next(url_iter)

                futures.append(exe.submit(_curl_flood_worker, url))

            for f in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break

                used_url = f.result()
                all_used_urls.append(used_url)
                log_buffer.append(used_url)

                if len(log_buffer) >= 100:
                    logger.info("CURL Batch:\n" + "\n".join([f"  -> {u}" for u in log_buffer]))
                    log_buffer = []

                completed += 1
                if completed % milestone == 0:
                    pct = int((completed / count) * 100)
                    logger.info(f"CURL Flood progress: {pct}%")

        if log_buffer:
            logger.info("CURL Batch:\n" + "\n".join([f"  -> {u}" for u in log_buffer]))

    logger.info("CURL Flood finished.")
    return all_used_urls

class VirtualFile(io.BytesIO):
    def __init__(self, size):
        self._size = size
        self._pos = 0
        super().__init__()

    def read(self, size=-1):
        if self._pos >= self._size:
            return b''
        if size == -1 or size is None:
            size = self._size - self._pos
        else:
            size = min(size, self._size - self._pos)

        self._pos += size
        return b'0' * size

    def seek(self, pos, whence=0):
        if whence == 0:
            self._pos = pos
        elif whence == 1:
            self._pos += pos
        elif whence == 2:
            self._pos = self._size + pos
        self._pos = max(0, min(self._pos, self._size))
        return self._pos

    def tell(self):
        return self._pos

def _ftp_worker(
    target,
    port,
    user,
    password,
    file_size_mb,
    is_ftps,
    attempt_label: str = "",
    protocol: str = "FTP"
) -> bool:
    ftp = None
    filename = f"upload_{random.randint(1000, 9999)}.bin"
    size_bytes = int(file_size_mb * 1024 * 1024)
    start_time = time.time()

    prefix = f"[{protocol}]"
    if attempt_label:
        prefix = f"[{protocol} {attempt_label}]"

    logger.info(
        f"{prefix} Start upload {filename} ({file_size_mb} MB) -> {target}:{port}"
    )

    try:
        if is_ftps:
            ftp = ftplib.FTP_TLS()
        else:
            ftp = ftplib.FTP()

        ftp.connect(target, port, timeout=10)
        ftp.login(user, password)

        if is_ftps:
            ftp.prot_p()

        mode_options = [True, False]
        upload_response = None
        upload_error = None

        for use_pasv in mode_options:
            mode_name = "passive" if use_pasv else "active"
            ftp.set_pasv(use_pasv)
            logger.info(f"{prefix} Trying {mode_name} mode for {filename}")

            try:
                vfile = VirtualFile(size_bytes)
                upload_response = ftp.storbinary(f"STOR {filename}", vfile)
                upload_error = None
                break
            except Exception as mode_exc:
                upload_error = mode_exc
                logger.warning(
                    f"{prefix} {mode_name} mode failed for {filename}, "
                    f"error={type(mode_exc).__name__}: {mode_exc}"
                )

        if upload_response is None:
            raise upload_error if upload_error else RuntimeError("Upload failed")

        elapsed = time.time() - start_time
        logger.info(
            f"{prefix} Upload SUCCESS {filename}, bytes={size_bytes}, "
            f"elapsed={elapsed:.2f}s, response={upload_response}"
        )

        try:
            delete_response = ftp.delete(filename)
            logger.info(
                f"{prefix} Cleanup delete SUCCESS {filename}, response={delete_response}"
            )
        except Exception:
            logger.warning(f"{prefix} Cleanup delete FAILED {filename}")

        ftp.quit()
        return True
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.warning(
            f"{prefix} Upload FAILED {filename}, bytes={size_bytes}, "
            f"elapsed={elapsed:.2f}s, error={type(exc).__name__}: {exc}"
        )
        return False
    finally:
        if ftp:
            try:
                ftp.close()
            except Exception:
                pass

def generate_ftp_traffic(
    target, port, user, password, file_size_mb,
    count, duration, concurrency, stop_event, is_ftps=False
) -> None:
    concurrency = max(1, concurrency)

    protocol = "FTPS" if is_ftps else "FTP"
    msg = f"{protocol} Traffic: {target}:{port}, Size: {file_size_mb}MB"
    if duration > 0:
        msg += f", duration {duration}s"
    else:
        msg += f", count {count}"
    logger.info(msg)

    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0
    attempted = 0
    completed = 0
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
        futures = []
        attempt_counter = itertools.count(1)

        def _worker_wrapper(attempt_label: str = ""):
            return _ftp_worker(
                target,
                port,
                user,
                password,
                file_size_mb,
                is_ftps,
                attempt_label,
                protocol,
            )

        if duration > 0:
            def _time_worker():
                while time.time() < end_time:
                    nonlocal attempted, completed, failed
                    if _is_stopped(stop_event):
                        break

                    attempt_no = next(attempt_counter)
                    attempt_label = str(attempt_no)
                    ok = _worker_wrapper(attempt_label)

                    attempted += 1
                    if ok:
                        completed += 1
                    else:
                        failed += 1

            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))
            concurrent.futures.wait(futures)
        else:
            for i in range(count):
                if _is_stopped(stop_event):
                    break
                attempt_label = f"{i + 1}/{count}"
                futures.append(exe.submit(_worker_wrapper, attempt_label))

            attempted = len(futures)
            progress_milestone = max(1, int(attempted * 0.2)) if attempted > 0 else 1

            for f in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                if f.result():
                    completed += 1
                else:
                    failed += 1

                done = completed + failed
                if done % progress_milestone == 0 or done == attempted:
                    logger.info(
                        f"{protocol} progress: completed={done}/{attempted}, "
                        f"success={completed}, failed={failed}"
                    )

    logger.info(
        f"{protocol} finished. attempted={attempted}, "
        f"success={completed}, failed={failed}"
    )

def generate_ftps_traffic(
    target, port, user, password, file_size_mb,
    count, duration, concurrency, stop_event
) -> None:
    generate_ftp_traffic(
        target, port, user, password, file_size_mb,
        count, duration, concurrency, stop_event, is_ftps=True
    )

def _sftp_worker(
    target,
    port,
    user,
    password,
    file_size_mb,
    attempt_label: str = "",
    protocol: str = "SFTP"
) -> bool:
    transport = None
    sock = None
    sftp = None
    filename = f"upload_{random.randint(1000, 9999)}.bin"
    size_bytes = int(file_size_mb * 1024 * 1024)
    start_time = time.time()

    prefix = f"[{protocol}]"
    if attempt_label:
        prefix = f"[{protocol} {attempt_label}]"

    logger.info(
        f"{prefix} Start upload {filename} ({file_size_mb} MB) -> {target}:{port}"
    )

    try:
        connect_attempts = 2
        connect_timeout_sec = 15
        last_error = None

        for attempt in range(1, connect_attempts + 1):
            try:
                sock = socket.create_connection(
                    (target, port), timeout=connect_timeout_sec
                )
                sock.settimeout(connect_timeout_sec)

                transport = paramiko.Transport(sock)
                transport.banner_timeout = connect_timeout_sec
                transport.auth_timeout = connect_timeout_sec
                transport.connect(username=user, password=password)
                transport.set_keepalive(15)
                break
            except Exception as conn_exc:
                last_error = conn_exc
                logger.warning(
                    f"{prefix} Connect/auth attempt {attempt}/{connect_attempts} failed, "
                    f"error={type(conn_exc).__name__}: {conn_exc}"
                )
                if transport:
                    try:
                        transport.close()
                    except Exception:
                        pass
                    transport = None
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    sock = None

        if transport is None:
            raise last_error if last_error else RuntimeError("SFTP connect/auth failed")

        sftp = paramiko.SFTPClient.from_transport(transport)

        vfile = VirtualFile(size_bytes)

        sftp.putfo(vfile, filename)
        elapsed = time.time() - start_time
        logger.info(
            f"{prefix} Upload SUCCESS {filename}, bytes={size_bytes}, "
            f"elapsed={elapsed:.2f}s"
        )

        try:
            sftp.remove(filename)
            logger.info(f"{prefix} Cleanup delete SUCCESS {filename}")
        except Exception as delete_exc:
            logger.warning(
                f"{prefix} Cleanup delete FAILED {filename}, "
                f"error={type(delete_exc).__name__}: {delete_exc}"
            )

        return True
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.warning(
            f"{prefix} Upload FAILED {filename}, bytes={size_bytes}, "
            f"elapsed={elapsed:.2f}s, error={type(exc).__name__}: {exc}"
        )
        return False
    finally:
        if sftp:
            sftp.close()
        if transport:
            transport.close()
        if sock:
            sock.close()

def generate_sftp_traffic(
    target, port, user, password, file_size_mb,
    count, duration, concurrency, stop_event
) -> None:
    concurrency = max(1, concurrency)

    msg = f"SFTP Traffic: {target}:{port}, Size: {file_size_mb}MB"
    if duration > 0:
        msg += f", duration {duration}s"
    else:
        msg += f", count {count}"
    logger.info(msg)

    start_time = time.time()
    end_time = start_time + duration if duration > 0 else 0
    attempted = 0
    completed = 0
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as exe:
        futures = []
        attempt_counter = itertools.count(1)

        if duration > 0:
            def _time_worker():
                nonlocal attempted, completed, failed
                while time.time() < end_time:
                    if _is_stopped(stop_event):
                        break

                    attempt_no = next(attempt_counter)
                    attempt_label = str(attempt_no)
                    ok = _sftp_worker(
                        target,
                        port,
                        user,
                        password,
                        file_size_mb,
                        attempt_label,
                        "SFTP",
                    )

                    attempted += 1
                    if ok:
                        completed += 1
                    else:
                        failed += 1

            for _ in range(concurrency):
                futures.append(exe.submit(_time_worker))
            concurrent.futures.wait(futures)
        else:
            for i in range(count):
                if _is_stopped(stop_event):
                    break
                attempt_label = f"{i + 1}/{count}"
                futures.append(exe.submit(
                    _sftp_worker,
                    target,
                    port,
                    user,
                    password,
                    file_size_mb,
                    attempt_label,
                    "SFTP",
                ))

            attempted = len(futures)
            progress_milestone = max(1, int(attempted * 0.2)) if attempted > 0 else 1

            for f in concurrent.futures.as_completed(futures):
                if _is_stopped(stop_event):
                    exe.shutdown(wait=False, cancel_futures=True)
                    break
                if f.result():
                    completed += 1
                else:
                    failed += 1

                done = completed + failed
                if done % progress_milestone == 0 or done == attempted:
                    logger.info(
                        f"SFTP progress: completed={done}/{attempted}, "
                        f"success={completed}, failed={failed}"
                    )

    logger.info(
        f"SFTP finished. attempted={attempted}, "
        f"success={completed}, failed={failed}"
    )

def get_hostname_from_url(url: str) -> str:
    try:
        hostname = url.strip()
        if hostname.lower().startswith("https://"):
            hostname = hostname[8:]
        elif hostname.lower().startswith("http://"):
            hostname = hostname[7:]

        hostname = hostname.split('/')[0]
        hostname = hostname.split(':')[0]
        return hostname
    except Exception:
        return ""
