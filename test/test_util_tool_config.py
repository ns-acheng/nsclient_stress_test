import json
import os
from unittest.mock import patch

import pytest

from util_tool_config import ToolConfig


@pytest.fixture
def write_config(tmp_path):
    def _write(config_data, state_data=None):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps(config_data), encoding="utf-8")
        if state_data is not None:
            state = tmp_path / "state.json"
            state.write_text(
                json.dumps(state_data), encoding="utf-8"
            )
        return str(cfg)

    return _write


def _make_tc(config_path, tmp_path):
    tc = ToolConfig(config_path)
    tc.state_file = str(tmp_path / "state.json")
    return tc


class TestToolConfigInit:
    def test_defaults_set(self):
        tc = ToolConfig("dummy.json")
        assert tc.loop_times == 1000
        assert tc.stop_svc_interval == 1
        assert tc.dns_enabled is False
        assert tc.browser_max_tabs == 20
        assert tc.ftp_target_port == 21
        assert tc.sftp_target_port == 2222

    def test_traffic_map_has_six_entries(self):
        assert len(ToolConfig.TRAFFIC_MAP) == 6
        keys = [m["json_key"] for m in ToolConfig.TRAFFIC_MAP]
        assert set(keys) == {
            "dns", "udp", "https", "ftp", "ftps", "sftp"
        }

    def test_range_constraints_defined(self):
        for attr, min_v, max_v, default in ToolConfig.RANGE_CONSTRAINTS:
            assert min_v <= default <= max_v

    def test_traffic_validation_defined(self):
        assert len(ToolConfig.TRAFFIC_VALIDATION) == 7
        names = [t[0] for t in ToolConfig.TRAFFIC_VALIDATION]
        assert "DNS" in names
        assert "AB" in names


class TestToolConfigLoad:
    def test_load_minimal(self, tmp_path, write_config, minimal_config):
        path = write_config(minimal_config)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.loop_times == 10
        assert tc.stop_svc_interval == 1
        assert tc.curl_flood_enabled is True
        assert tc.curl_flood_count == 60
        assert tc.curl_flood_concurrent == 30

    def test_load_full(self, tmp_path, write_config, full_config):
        path = write_config(full_config)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.loop_times == 50
        assert tc.failclose_enabled is True
        assert tc.failclose_interval == 15
        assert tc.client_disabling_enabled is False
        assert tc.client_enable_min == 200
        assert tc.client_enable_max == 800
        assert tc.client_disable_ratio == 0.2
        assert tc.browser_max_memory == 70
        assert tc.browser_max_tabs == 15
        assert tc.dns_enabled is True
        assert tc.dns_count == 100
        assert tc.ftp_enabled is True
        assert tc.ftp_target_ip == "127.0.0.1"

    def test_load_state_file(self, tmp_path, write_config, minimal_config):
        state = {"cur_iter": 42, "cur_log_dir": "log/test"}
        path = write_config(minimal_config, state)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.cur_iter == 42
        assert tc.cur_log_dir == "log/test"

    def test_load_missing_state_uses_defaults(
        self, tmp_path, write_config, minimal_config
    ):
        path = write_config(minimal_config)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.cur_iter == 0
        assert tc.cur_log_dir == ""

    def test_load_missing_config_exits(self, tmp_path):
        tc = _make_tc("nonexistent.json", tmp_path)
        with pytest.raises(SystemExit):
            tc.load()

    def test_load_invalid_json_exits(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid json", encoding="utf-8")
        tc = _make_tc(str(bad), tmp_path)
        with pytest.raises(SystemExit):
            tc.load()

    def test_load_corrupt_state_still_loads(
        self, tmp_path, write_config, minimal_config
    ):
        path = write_config(minimal_config)
        state_file = tmp_path / "state.json"
        state_file.write_text("not json", encoding="utf-8")
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.cur_iter == 0

    def test_ab_disabled_zeroes_conn(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 5,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
            "traffic_gen": {
                "ab": {
                    "enable": 0,
                    "duration_sec": 100,
                    "total_conn": 5000,
                    "concurrent_conn": 50,
                },
                "https": {
                    "enable": 1,
                    "count": 10,
                    "duration_sec": 0,
                    "concurrent_conn": 20,
                },
            },
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.ab_total_conn == 0
        assert tc.ab_duration == 0

    def test_ab_target_urls_string_to_list(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 5,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
            "traffic_gen": {
                "ab": {
                    "enable": 1,
                    "duration_sec": 10,
                    "total_conn": 100,
                    "concurrent_conn": 20,
                    "target_urls": "http://single.url/",
                },
                "https": {
                    "enable": 1,
                    "count": 10,
                    "duration_sec": 0,
                    "concurrent_conn": 20,
                },
            },
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert isinstance(tc.ab_target_urls, list)
        assert tc.ab_target_urls == ["http://single.url/"]


class TestToolConfigSave:
    def test_save_persists_state(
        self, tmp_path, write_config, minimal_config
    ):
        path = write_config(minimal_config)
        tc = _make_tc(path, tmp_path)
        tc.load()
        tc.cur_iter = 99
        tc.cur_log_dir = "log/saved"
        tc.save()

        state_file = tmp_path / "state.json"
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert saved["cur_iter"] == 99
        assert saved["cur_log_dir"] == "log/saved"

    def test_save_includes_python_path(
        self, tmp_path, write_config, minimal_config
    ):
        path = write_config(minimal_config)
        tc = _make_tc(path, tmp_path)
        tc.load()
        tc.save()

        state_file = tmp_path / "state.json"
        saved = json.loads(state_file.read_text(encoding="utf-8"))
        assert "python_path" in saved


class TestValidation:
    def test_invalid_loop_times_exits(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": -1,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        with pytest.raises(SystemExit):
            tc.load()

    def test_zero_loop_times_exits(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 0,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        with pytest.raises(SystemExit):
            tc.load()

    def test_negative_stop_svc_interval_exits(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 1,
            "stop_svc_interval": -1,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        with pytest.raises(SystemExit):
            tc.load()

    def test_negative_reboot_interval_exits(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 1,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": -1,
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        with pytest.raises(SystemExit):
            tc.load()

    def test_range_constraint_clamps_to_default(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 5,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
            "traffic_gen": {
                "browser": {"enable": 1, "max_tabs": 9999},
                "https": {
                    "enable": 1,
                    "count": 10,
                    "duration_sec": 0,
                    "concurrent_conn": 20,
                },
            },
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.browser_max_tabs == 20

    def test_client_enable_max_adjusted_to_min(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 5,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
            "client_feature_toggling": {
                "client_disabling": {
                    "enable": 0,
                    "enable_sec_min": 500,
                    "enable_sec_max": 200,
                    "disable_ratio": 0.1,
                }
            },
            "traffic_gen": {
                "https": {
                    "enable": 1,
                    "count": 10,
                    "duration_sec": 0,
                    "concurrent_conn": 20,
                }
            },
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.client_enable_max >= tc.client_enable_min

    def test_long_idle_max_adjusted_to_min(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 5,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
            "long_idle_time_min": 600,
            "long_idle_time_max": 400,
            "traffic_gen": {
                "https": {
                    "enable": 1,
                    "count": 10,
                    "duration_sec": 0,
                    "concurrent_conn": 20,
                }
            },
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.long_idle_time_max >= tc.long_idle_time_min


class TestCapDurationCount:
    def test_normal_values_unchanged(self):
        tc = ToolConfig("dummy.json")
        d, c = tc._cap_duration_count(100, 500, "TEST")
        assert d == 100
        assert c == 500

    def test_duration_capped_at_21600(self):
        tc = ToolConfig("dummy.json")
        d, c = tc._cap_duration_count(99999, 100, "TEST")
        assert d == 21600

    def test_count_capped_at_2b(self):
        tc = ToolConfig("dummy.json")
        d, c = tc._cap_duration_count(100, 3_000_000_000, "TEST")
        assert c == 2_000_000_000


class TestCapConcurrency:
    def test_ftp_min_1(self):
        tc = ToolConfig("dummy.json")
        assert tc._cap_concurrency(0, "FTP") == 1
        assert tc._cap_concurrency(0, "FTPS") == 1
        assert tc._cap_concurrency(0, "SFTP") == 1

    def test_ftp_max_50(self):
        tc = ToolConfig("dummy.json")
        assert tc._cap_concurrency(100, "FTP") == 50
        assert tc._cap_concurrency(100, "FTPS") == 50
        assert tc._cap_concurrency(100, "SFTP") == 50

    def test_ftp_in_range_unchanged(self):
        tc = ToolConfig("dummy.json")
        assert tc._cap_concurrency(25, "FTP") == 25

    def test_general_min_10(self):
        tc = ToolConfig("dummy.json")
        assert tc._cap_concurrency(1, "DNS") == 10
        assert tc._cap_concurrency(5, "HTTPS") == 10

    def test_general_max_1024(self):
        tc = ToolConfig("dummy.json")
        assert tc._cap_concurrency(2000, "DNS") == 1024

    def test_general_in_range_unchanged(self):
        tc = ToolConfig("dummy.json")
        assert tc._cap_concurrency(100, "DNS") == 100


class TestValidateTrafficSection:
    def test_disabled_returns_false(self):
        tc = ToolConfig("dummy.json")
        assert tc._validate_traffic_section(False, 10, 10, "X") is False

    def test_both_zero_returns_false(self):
        tc = ToolConfig("dummy.json")
        assert tc._validate_traffic_section(True, 0, 0, "X") is False

    def test_duration_only_returns_true(self):
        tc = ToolConfig("dummy.json")
        assert tc._validate_traffic_section(True, 10, 0, "X") is True

    def test_count_only_returns_true(self):
        tc = ToolConfig("dummy.json")
        assert tc._validate_traffic_section(True, 0, 10, "X") is True

    def test_both_positive_returns_true(self):
        tc = ToolConfig("dummy.json")
        assert tc._validate_traffic_section(True, 10, 10, "X") is True


class TestTrafficDisabledOnInvalidConfig:
    def test_dns_count_zero_clamped_stays_enabled(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 5,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
            "traffic_gen": {
                "dns": {
                    "enable": 1,
                    "duration_sec": 0,
                    "count": 0,
                    "concurrent_conn": 20,
                },
                "https": {
                    "enable": 1,
                    "count": 10,
                    "duration_sec": 0,
                    "concurrent_conn": 20,
                },
            },
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.dns_count == 50
        assert tc.dns_enabled is True

    def test_https_disabled_when_both_zero(
        self, tmp_path, write_config
    ):
        cfg = {
            "loop_times": 5,
            "stop_svc_interval": 0,
            "stop_drv_interval": 0,
            "reboot_interval": 0,
            "traffic_gen": {
                "https": {
                    "enable": 1,
                    "duration_sec": 0,
                    "count": 0,
                    "concurrent_conn": 20,
                },
            },
        }
        path = write_config(cfg)
        tc = _make_tc(path, tmp_path)
        tc.load()
        assert tc.curl_flood_enabled is False


class TestJSONCommentStripping:
    """Test that // comments are properly handled in config.json"""

    def test_inline_comments_are_removed(self, tmp_path):
        """Test that inline // comments after valid JSON are stripped"""
        json_with_comments = '''{
    "loop_times": 100, // this is a comment
    "stop_svc_interval": 5  // another comment
}'''
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json_with_comments, encoding="utf-8")

        tc = _make_tc(str(cfg_file), tmp_path)
        tc.load()

        assert tc.loop_times == 100
        assert tc.stop_svc_interval == 5

    def test_full_line_comments_are_removed(self, tmp_path):
        """Test that full-line // comments are stripped"""
        json_with_comments = '''{
    // This is a full line comment
    "loop_times": 200,
    // Another full line comment
    "stop_svc_interval": 10
}'''
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json_with_comments, encoding="utf-8")

        tc = _make_tc(str(cfg_file), tmp_path)
        tc.load()

        assert tc.loop_times == 200
        assert tc.stop_svc_interval == 10

    def test_urls_are_preserved(self, tmp_path):
        """Test that http:// and https:// in URLs are preserved"""
        json_with_urls = '''{
    "loop_times": 50,
    "traffic_gen": {
        "ab": {
            "enable": 1,
            "total_conn": 1000,
            "concurrent_conn": 50,
            "duration_sec": 0,
            "target_urls": [
                "http://example.com/test",
                "https://secure.example.com/api"
            ]
        }
    }
}'''
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json_with_urls, encoding="utf-8")

        tc = _make_tc(str(cfg_file), tmp_path)
        tc.load()

        assert tc.loop_times == 50
        assert tc.ab_target_urls == [
            "http://example.com/test",
            "https://secure.example.com/api"
        ]

    def test_double_slash_in_strings_preserved(self, tmp_path):
        """Test that // inside JSON string values is preserved"""
        json_with_string_slashes = '''{
    "loop_times": 75,
    "custom_dump_path": "/tmp/dump/file.dmp",
    "traffic_gen": {
        "ftp": {
            "enable": 0,
            "target_ip": "127.0.0.1",
            "user": "test//user",
            "password": "pass//word"
        }
    }
}'''
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json_with_string_slashes, encoding="utf-8")

        tc = _make_tc(str(cfg_file), tmp_path)
        tc.load()

        assert tc.loop_times == 75
        assert tc.custom_dump_path == "/tmp/dump/file.dmp"
        assert tc.ftp_user == "test//user"
        assert tc.ftp_password == "pass//word"

    def test_mixed_comments_and_urls(self, tmp_path):
        """Test complex case with comments and URLs together"""
        json_complex = '''{
    // Configuration for stress test
    "loop_times": 300, // number of iterations
    "stop_svc_interval": 0,
    "traffic_gen": {
        // Browser configuration
        "browser": {
            "enable": 1,
            "max_memory": 80,
            "max_tabs": 30
        },
        "ab": {
            "enable": 1, // enable apache benchmark
            "total_conn": 5000,
            "concurrent_conn": 100,
            "target_urls": [
                "http://localhost/test", // local test server
                "https://example.com/api" // external API
            ]
        }
        // End of traffic_gen
    }
}'''
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json_complex, encoding="utf-8")

        tc = _make_tc(str(cfg_file), tmp_path)
        tc.load()

        assert tc.loop_times == 300
        assert tc.stop_svc_interval == 0
        assert tc.enable_browser_tabs_open == 1  # Config returns int, not bool
        assert tc.browser_max_memory == 80
        assert tc.browser_max_tabs == 30
        assert tc.ab_total_conn == 5000
        assert tc.ab_concurrent == 100
        assert len(tc.ab_target_urls) == 2
        assert "http://localhost/test" in tc.ab_target_urls
        assert "https://example.com/api" in tc.ab_target_urls

    def test_comment_at_end_of_object(self, tmp_path):
        """Test that comments at end of objects are handled"""
        json_with_comment = '''{
    "loop_times": 25,
    "stop_svc_interval": 5 // comment at end
}'''
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json_with_comment, encoding="utf-8")

        tc = _make_tc(str(cfg_file), tmp_path)
        tc.load()

        assert tc.loop_times == 25
        assert tc.stop_svc_interval == 5

    def test_multiple_consecutive_backslashes(self, tmp_path):
        """Test handling of multiple backslashes before quotes"""
        json_data = '''{
        "path": "C:\\\\\\\\test",
        "loop_times": 10
    }'''
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json_data, encoding="utf-8")

        tc = _make_tc(str(cfg_file), tmp_path)
        tc.load()

        assert tc.loop_times == 10
        # path should be "C:\\\\test" after JSON parsing
