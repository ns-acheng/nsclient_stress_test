import json
import os
import threading
from unittest.mock import patch, MagicMock

import pytest

import util_validate
from util_validate import (
    NsClientLogValidator,
    init_validator,
    get_validator,
    check_nsclient_log,
    check_nsclient_log_regex,
    check_tunneling_in_text,
    validate_traffic_flow,
)


@pytest.fixture
def log_env(tmp_path):
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "data").mkdir()
    log_file = agent_dir / "nsclient.log"
    log_file.write_text("", encoding="utf-8")
    env = MagicMock()
    env.agent_data_dir = str(agent_dir)
    env.agent_log_file = str(log_file)
    env.system_hosts_file = str(tmp_path / "hosts")
    return env


@pytest.fixture
def validator(log_env):
    return NsClientLogValidator(log_env)


@pytest.fixture(autouse=True)
def reset_singleton():
    util_validate._validator = None
    yield
    util_validate._validator = None


class TestNsClientLogValidatorInit:
    def test_paths_set(self, validator, log_env):
        assert validator.log_path == log_env.agent_log_file
        assert validator.last_pos == 0

    def test_lock_created(self, validator):
        assert isinstance(validator.lock, type(threading.Lock()))


class TestGetSteeringConfig:
    def test_loads_json(self, validator):
        sc_path = os.path.join(
            validator.stagent_path, "data", "nssteering.json"
        )
        data = {"firewall_traffic_mode": "all", "version": 1}
        with open(sc_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        result = validator.get_steering_config()
        assert result["firewall_traffic_mode"] == "all"

    def test_missing_file(self, validator):
        assert validator.get_steering_config() == {}

    def test_invalid_json(self, validator):
        sc_path = os.path.join(
            validator.stagent_path, "data", "nssteering.json"
        )
        with open(sc_path, "w", encoding="utf-8") as f:
            f.write("{bad")
        assert validator.get_steering_config() == {}


class TestUpdatePosToEnd:
    def test_advances_to_eof(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("line1\nline2\nline3\n")
        validator.update_pos_to_end()
        assert validator.last_pos == os.path.getsize(validator.log_path)

    def test_missing_log(self, validator):
        os.remove(validator.log_path)
        validator.update_pos_to_end()
        assert validator.last_pos == 0


class TestCheckLog:
    def test_plain_text_found(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("some log TUNNEL_FOUND here\n")
        assert validator.check_log("TUNNEL_FOUND", is_regex=False) is True

    def test_plain_text_not_found(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("some log line\n")
        assert validator.check_log("MISSING_PATTERN", is_regex=False) is False

    def test_regex_found(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("Tunneling flow from addr: 1.2.3.4\n")
        assert validator.check_log(
            r"Tunneling flow from addr: \d+\.\d+\.\d+\.\d+",
            is_regex=True,
        ) is True

    def test_regex_not_found(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("some other log\n")
        assert validator.check_log(r"^NEVER_MATCH$", is_regex=True) is False

    def test_skips_old_content(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("old content FIND_ME\n")
        validator.update_pos_to_end()

        with open(validator.log_path, "a", encoding="utf-8") as f:
            f.write("new content\n")
        assert validator.check_log("FIND_ME", is_regex=False) is False

    def test_finds_new_content_after_pos_update(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("old line\n")
        validator.update_pos_to_end()

        with open(validator.log_path, "a", encoding="utf-8") as f:
            f.write("new line TARGET\n")
        assert validator.check_log("TARGET", is_regex=False) is True


class TestReadNewLogs:
    def test_reads_new_content(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("old line\n")
        validator.update_pos_to_end()

        with open(validator.log_path, "a", encoding="utf-8") as f:
            f.write("new line\n")
        content = validator.read_new_logs()
        assert "new line" in content
        assert "old line" not in content

    def test_empty_when_no_new(self, validator):
        with open(validator.log_path, "w", encoding="utf-8") as f:
            f.write("data\n")
        validator.update_pos_to_end()
        content = validator.read_new_logs()
        assert content == ""


class TestSingletonFunctions:
    def test_init_and_get(self, log_env):
        init_validator(log_env)
        v = get_validator()
        assert isinstance(v, NsClientLogValidator)

    def test_get_before_init_raises(self):
        with pytest.raises(RuntimeError):
            get_validator()

    def test_init_idempotent(self, log_env):
        init_validator(log_env)
        v1 = get_validator()
        init_validator(log_env)
        v2 = get_validator()
        assert v1 is v2


class TestCheckNsclientLog:
    def test_plain(self, log_env):
        init_validator(log_env)
        log_file = log_env.agent_log_file
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("hello world\n")
        assert check_nsclient_log("hello") is True
        assert check_nsclient_log("missing") is False

    def test_regex(self, log_env):
        init_validator(log_env)
        log_file = log_env.agent_log_file
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("count=42\n")
        assert check_nsclient_log_regex(r"count=\d+") is True
        assert check_nsclient_log_regex(r"^XYZ$") is False


class TestCheckTunnelingInText:
    def test_tunneling_found(self):
        text = (
            "Tunneling flow from addr: 1.2.3.4, "
            "process: curl.exe to host: example.com, port: 443"
        )
        assert check_tunneling_in_text(
            "curl.exe", "https://example.com/page", text
        ) is True

    def test_bypass_found(self):
        text = (
            "bypassing flow to exception host: example.com, "
            "process: curl.exe"
        )
        assert check_tunneling_in_text(
            "curl.exe", "https://example.com/page", text
        ) is True

    def test_not_found(self):
        text = "some unrelated log line"
        assert check_tunneling_in_text(
            "curl.exe", "https://example.com", text
        ) is False

    def test_empty_url(self):
        assert check_tunneling_in_text("curl.exe", "", "text") is False

    def test_empty_text(self):
        assert check_tunneling_in_text(
            "curl.exe", "https://example.com", ""
        ) is False

    def test_url_no_scheme(self):
        text = (
            "Tunneling flow from addr: 1.2.3.4, "
            "process: curl.exe to host: example.com:443"
        )
        assert check_tunneling_in_text(
            "curl.exe", "example.com", text
        ) is True


class TestValidateTrafficFlow:
    @patch("util_validate.get_validator")
    @patch("util_validate.smart_sleep", return_value=False)
    def test_empty_map_returns_true(self, mock_sleep, mock_gv):
        assert validate_traffic_flow({}, threading.Event()) is True

    @patch("util_validate.get_validator")
    @patch("util_validate.smart_sleep", return_value=False)
    def test_http_urls_auto_pass(self, mock_sleep, mock_gv):
        pmap = {"curl.exe": ["http://example.com"]}
        assert validate_traffic_flow(pmap, threading.Event()) is True

    @patch("util_validate.get_validator")
    @patch("util_validate.smart_sleep", return_value=False)
    def test_exception_urls_pass(self, mock_sleep, mock_gv):
        checker = lambda url: True
        pmap = {"curl.exe": ["https://exception.com"]}
        assert validate_traffic_flow(
            pmap, threading.Event(), exception_checker=checker
        ) is True

    @patch("util_validate.util_cert.check_url_cert")
    @patch("util_validate.get_validator")
    @patch("util_validate.smart_sleep", return_value=False)
    def test_log_match_passes(self, mock_sleep, mock_gv, mock_cert):
        mock_validator = MagicMock()
        mock_validator.read_new_logs.return_value = (
            "Tunneling flow from addr: 1.2.3.4, "
            "process: curl.exe to host: example.com, port: 443"
        )
        mock_gv.return_value = mock_validator

        pmap = {"curl.exe": ["https://example.com"]}
        result = validate_traffic_flow(pmap, threading.Event())
        assert result is True

    @patch("util_validate.util_cert.check_url_cert")
    @patch("util_validate.get_validator")
    @patch("util_validate.smart_sleep", return_value=False)
    def test_cert_fallback_passes(self, mock_sleep, mock_gv, mock_cert):
        mock_validator = MagicMock()
        mock_validator.read_new_logs.return_value = "unrelated logs"
        mock_gv.return_value = mock_validator
        mock_cert.return_value = "CN=proxy.boomskope.com"

        pmap = {"curl.exe": ["https://example.com"]}
        result = validate_traffic_flow(pmap, threading.Event())
        assert result is True

    @patch("util_validate.util_cert.check_url_cert")
    @patch("util_validate.get_validator")
    @patch("util_validate.smart_sleep", return_value=False)
    def test_all_fail(self, mock_sleep, mock_gv, mock_cert):
        mock_validator = MagicMock()
        mock_validator.read_new_logs.return_value = ""
        mock_gv.return_value = mock_validator
        mock_cert.return_value = "CN=some-other-ca.com"

        pmap = {"curl.exe": ["https://example.com"]}
        result = validate_traffic_flow(pmap, threading.Event())
        assert result is False

    @patch("util_validate.get_validator")
    @patch("util_validate.smart_sleep", return_value=True)
    def test_stop_event_aborts(self, mock_sleep, mock_gv):
        mock_validator = MagicMock()
        mock_validator.read_new_logs.return_value = ""
        mock_gv.return_value = mock_validator

        pmap = {"curl.exe": ["https://example.com"]}
        result = validate_traffic_flow(pmap, threading.Event())
        assert result is False
