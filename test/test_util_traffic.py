import io
import os
import socket
import threading
import time
from unittest.mock import patch, MagicMock, mock_open

import pytest

import util_traffic
from util_traffic import (
    get_hostname_from_url,
    read_urls_from_file,
    check_url_alive,
    get_system_memory_usage,
    _is_stopped,
    VirtualFile,
    generate_dns_flood,
    generate_udp_flood,
    curl_requests,
    generate_curl_flood,
    generate_ftp_traffic,
    generate_ftps_traffic,
    generate_sftp_traffic,
    log_resource_usage,
    open_browser_tabs,
)


class TestGetHostnameFromUrl:
    def test_https(self):
        assert get_hostname_from_url("https://example.com/path") == "example.com"

    def test_http(self):
        assert get_hostname_from_url("http://example.com/page") == "example.com"

    def test_with_port(self):
        assert get_hostname_from_url("https://example.com:8443/api") == "example.com"

    def test_no_scheme(self):
        assert get_hostname_from_url("example.com/page") == "example.com"

    def test_empty_string(self):
        assert get_hostname_from_url("") == ""

    def test_whitespace_stripped(self):
        assert get_hostname_from_url("  https://example.com  ") == "example.com"

    def test_trailing_slash_only(self):
        assert get_hostname_from_url("https://example.com/") == "example.com"


class TestIsStopped:
    def test_none_returns_false(self):
        assert _is_stopped(None) is False

    def test_not_set_returns_false(self):
        event = threading.Event()
        assert _is_stopped(event) is False

    def test_set_returns_true(self):
        event = threading.Event()
        event.set()
        assert _is_stopped(event) is True


class TestReadUrlsFromFile:
    def test_reads_lines(self, tmp_path):
        f = tmp_path / "urls.txt"
        f.write_text(
            "https://a.com\nhttps://b.com\n\nhttps://c.com\n",
            encoding="utf-8",
        )
        result = read_urls_from_file(str(f))
        assert result == ["https://a.com", "https://b.com", "https://c.com"]

    def test_strips_whitespace(self, tmp_path):
        f = tmp_path / "urls.txt"
        f.write_text("  https://a.com  \n  https://b.com  \n", encoding="utf-8")
        result = read_urls_from_file(str(f))
        assert result == ["https://a.com", "https://b.com"]

    def test_missing_file_returns_none(self):
        result = read_urls_from_file("nonexistent_file_xyz.txt")
        assert result is None

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = read_urls_from_file(str(f))
        assert result == []


class TestCheckUrlAlive:
    @patch("util_traffic.requests.head")
    def test_alive_returns_url(self, mock_head):
        resp = MagicMock()
        resp.status_code = 200
        resp.url = "https://example.com"
        mock_head.return_value = resp
        assert check_url_alive("https://example.com") == "https://example.com"

    @patch("util_traffic.requests.head")
    def test_redirect_returns_final(self, mock_head):
        resp = MagicMock()
        resp.status_code = 301
        resp.url = "https://www.example.com"
        mock_head.return_value = resp
        assert check_url_alive("https://example.com") == "https://www.example.com"

    @patch("util_traffic.requests.head")
    def test_403_treated_alive(self, mock_head):
        resp = MagicMock()
        resp.status_code = 403
        resp.url = "https://example.com"
        mock_head.return_value = resp
        assert check_url_alive("https://example.com") == "https://example.com"

    @patch("util_traffic.requests.head")
    def test_500_returns_empty(self, mock_head):
        resp = MagicMock()
        resp.status_code = 500
        resp.url = "https://example.com"
        mock_head.return_value = resp
        assert check_url_alive("https://example.com") == ""

    @patch("util_traffic.requests.head", side_effect=Exception("timeout"))
    def test_exception_returns_empty(self, mock_head):
        assert check_url_alive("https://example.com") == ""


class TestGetSystemMemoryUsage:
    @patch("util_traffic.psutil.virtual_memory")
    def test_returns_fraction(self, mock_vm):
        mock_vm.return_value = MagicMock(percent=75.0)
        result = get_system_memory_usage()
        assert result == pytest.approx(0.75)

    @patch("util_traffic.psutil.virtual_memory", side_effect=Exception("fail"))
    def test_returns_zero_on_error(self, mock_vm):
        assert get_system_memory_usage() == 0.0


class TestVirtualFile:
    def test_read_exact_size(self):
        vf = VirtualFile(1024)
        data = vf.read()
        assert len(data) == 1024
        assert data == b"0" * 1024

    def test_read_in_chunks(self):
        vf = VirtualFile(100)
        chunk1 = vf.read(40)
        chunk2 = vf.read(40)
        chunk3 = vf.read(40)
        assert len(chunk1) == 40
        assert len(chunk2) == 40
        assert len(chunk3) == 20

    def test_read_past_eof(self):
        vf = VirtualFile(10)
        vf.read()
        assert vf.read() == b""

    def test_seek_and_tell(self):
        vf = VirtualFile(100)
        vf.read(50)
        assert vf.tell() == 50
        vf.seek(0)
        assert vf.tell() == 0
        data = vf.read(100)
        assert len(data) == 100

    def test_seek_whence_end(self):
        vf = VirtualFile(100)
        vf.seek(-10, 2)
        assert vf.tell() == 90
        data = vf.read()
        assert len(data) == 10

    def test_mb_size(self):
        size = 1 * 1024 * 1024
        vf = VirtualFile(size)
        total = 0
        while True:
            chunk = vf.read(65536)
            if not chunk:
                break
            total += len(chunk)
        assert total == size


class TestGenerateDnsFlood:
    @patch("util_traffic._dns_worker")
    def test_count_mode(self, mock_worker, stop_event):
        generate_dns_flood(["example.com"], count=10, stop_event=stop_event)
        assert mock_worker.call_count == 10

    def test_empty_domains_returns(self, stop_event):
        generate_dns_flood([], count=10, stop_event=stop_event)

    @patch("util_traffic._dns_worker")
    def test_stop_event_halts_iteration(self, mock_worker, stop_event):
        stop_event.set()
        generate_dns_flood(
            ["example.com"], count=100,
            duration=5, concurrency=2, stop_event=stop_event,
        )
        assert mock_worker.call_count == 0

    @patch("util_traffic._dns_worker")
    def test_duration_mode(self, mock_worker, stop_event):
        def stop_soon():
            time.sleep(0.5)
            stop_event.set()

        t = threading.Thread(target=stop_soon)
        t.start()
        generate_dns_flood(
            ["example.com"], count=0, duration=10,
            concurrency=2, stop_event=stop_event,
        )
        t.join()
        assert mock_worker.call_count > 0


class TestGenerateUdpFlood:
    @patch("util_traffic.socket.socket")
    def test_count_mode(self, mock_sock_cls, stop_event):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        generate_udp_flood(
            "127.0.0.1", 9999, count=5,
            concurrency=1, stop_event=stop_event,
        )
        assert mock_sock.sendto.call_count == 5
        mock_sock.close.assert_called()

    @patch("util_traffic.socket.socket")
    def test_stop_event_halts(self, mock_sock_cls, stop_event):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        stop_event.set()
        generate_udp_flood(
            "127.0.0.1", 9999, count=1000,
            concurrency=1, stop_event=stop_event,
        )
        assert mock_sock.sendto.call_count == 0

    @patch("util_traffic.socket.socket")
    def test_count_mode_distributes_remainder(self, mock_sock_cls, stop_event):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        generate_udp_flood(
            "127.0.0.1", 9999, count=7,
            concurrency=3, stop_event=stop_event,
        )
        assert mock_sock.sendto.call_count == 7


class TestCurlRequests:
    @patch("util_traffic.run_curl")
    def test_calls_curl(self, mock_curl):
        urls = [f"https://site{i}.com" for i in range(20)]
        curl_requests(urls)
        assert mock_curl.call_count >= 2
        assert mock_curl.call_count <= 10

    @patch("util_traffic.run_curl")
    def test_includes_first_and_last(self, mock_curl):
        urls = ["https://first.com", "https://mid.com", "https://last.com"]
        curl_requests(urls)
        called_urls = [c.args[0] for c in mock_curl.call_args_list]
        assert "https://first.com" in called_urls
        assert "https://last.com" in called_urls

    @patch("util_traffic.run_curl")
    def test_empty_urls(self, mock_curl):
        curl_requests([])
        mock_curl.assert_not_called()

    @patch("util_traffic.run_curl")
    def test_stop_event(self, mock_curl, stop_event):
        stop_event.set()
        curl_requests(["https://a.com", "https://b.com"], stop_event=stop_event)
        assert mock_curl.call_count == 0


class TestGenerateCurlFlood:
    @patch("util_traffic._curl_flood_worker", return_value="https://a.com")
    def test_count_mode(self, mock_worker):
        urls = ["https://a.com", "https://b.com"]
        result = generate_curl_flood(urls, count=5, concurrency=2)
        assert len(result) == 5

    def test_empty_urls(self):
        result = generate_curl_flood([], count=10)
        assert result == []

    @patch("util_traffic._curl_flood_worker", return_value="https://a.com")
    def test_stop_event(self, mock_worker, stop_event):
        stop_event.set()
        result = generate_curl_flood(
            ["https://a.com"], count=100, stop_event=stop_event
        )
        assert len(result) < 100


class TestGenerateFtpTraffic:
    @patch("util_traffic._ftp_worker", return_value=True)
    def test_count_mode(self, mock_worker, stop_event):
        generate_ftp_traffic(
            "127.0.0.1", 21, "u", "p", 1,
            count=3, duration=0, concurrency=1, stop_event=stop_event,
        )
        assert mock_worker.call_count == 3

    @patch("util_traffic._ftp_worker", return_value=True)
    def test_stop_event(self, mock_worker, stop_event):
        stop_event.set()
        generate_ftp_traffic(
            "127.0.0.1", 21, "u", "p", 1,
            count=100, duration=0, concurrency=1, stop_event=stop_event,
        )
        assert mock_worker.call_count == 0


class TestGenerateFtpsTraffic:
    @patch("util_traffic.generate_ftp_traffic")
    def test_delegates_with_is_ftps(self, mock_ftp, stop_event):
        generate_ftps_traffic(
            "127.0.0.1", 990, "u", "p", 1,
            count=5, duration=0, concurrency=1, stop_event=stop_event,
        )
        mock_ftp.assert_called_once()
        assert mock_ftp.call_args.kwargs.get("is_ftps") is True or \
               mock_ftp.call_args[1].get("is_ftps") is True


class TestGenerateSftpTraffic:
    @patch("util_traffic._sftp_worker", return_value=True)
    def test_count_mode(self, mock_worker, stop_event):
        generate_sftp_traffic(
            "127.0.0.1", 2222, "u", "p", 1,
            count=3, duration=0, concurrency=1, stop_event=stop_event,
        )
        assert mock_worker.call_count == 3

    @patch("util_traffic._sftp_worker", return_value=True)
    def test_stop_event(self, mock_worker, stop_event):
        stop_event.set()
        generate_sftp_traffic(
            "127.0.0.1", 2222, "u", "p", 1,
            count=100, duration=0, concurrency=1, stop_event=stop_event,
        )
        assert mock_worker.call_count == 0


class TestLogResourceUsage:
    @patch("util_traffic.psutil.process_iter")
    def test_writes_log_file(self, mock_iter, tmp_path):
        proc_info = {
            "name": "stAgentSvc.exe",
            "cpu_percent": 12.5,
            "memory_info": MagicMock(rss=50 * 1024 * 1024),
        }
        mock_proc = MagicMock()
        mock_proc.info = proc_info
        mock_iter.return_value = [mock_proc]

        log_resource_usage("stAgentSvc.exe", str(tmp_path))

        log_file = tmp_path / "stAgentSvc.exe_resources.log"
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "12.5%" in content
        assert "50.0MB" in content


class TestOpenBrowserTabs:
    @patch("util_traffic.log_resource_usage")
    @patch("util_traffic.get_system_memory_usage", return_value=0.5)
    @patch("util_traffic.smart_sleep", return_value=False)
    @patch("util_traffic.run_batch")
    def test_opens_tabs(
        self, mock_batch, mock_sleep, mock_mem, mock_log, tmp_path
    ):
        urls = [f"https://site{i}.com" for i in range(20)]
        result = open_browser_tabs(
            urls, str(tmp_path), max_tabs=5,
            max_mem=90, stop_event=threading.Event(),
            log_dir=str(tmp_path), wait_sec=0,
        )
        assert len(result) <= 5
        assert mock_batch.call_count >= 1

    def test_empty_urls(self, stop_event, tmp_path):
        result = open_browser_tabs(
            [], str(tmp_path), max_tabs=10,
            max_mem=90, stop_event=stop_event,
            log_dir=str(tmp_path), wait_sec=0,
        )
        assert result == []

    @patch("util_traffic.log_resource_usage")
    @patch("util_traffic.get_system_memory_usage", return_value=0.95)
    @patch("util_traffic.smart_sleep", return_value=False)
    @patch("util_traffic.run_batch")
    def test_stops_on_memory_threshold(
        self, mock_batch, mock_sleep, mock_mem, mock_log, tmp_path
    ):
        urls = [f"https://site{i}.com" for i in range(50)]
        result = open_browser_tabs(
            urls, str(tmp_path), max_tabs=100,
            max_mem=90, stop_event=threading.Event(),
            log_dir=str(tmp_path), wait_sec=0,
        )
        assert mock_batch.call_count == 1
