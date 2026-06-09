import json
import os
import shutil
from unittest.mock import patch, MagicMock

import pytest

from util_config import AgentConfigManager


@pytest.fixture
def agent_dir(tmp_path):
    data_dir = tmp_path / "agent"
    data_dir.mkdir()
    (data_dir / "data").mkdir()
    return data_dir


@pytest.fixture
def hosts_file(tmp_path):
    f = tmp_path / "hosts"
    f.write_text(
        "# hosts file\n127.0.0.1 localhost\n",
        encoding="utf-8",
    )
    return f


@pytest.fixture
def cfg(agent_dir, hosts_file):
    env = MagicMock()
    env.agent_data_dir = str(agent_dir)
    env.agent_log_file = str(agent_dir / "nsclient.log")
    env.system_hosts_file = str(hosts_file)
    mgr = AgentConfigManager(env)
    mgr.hosts_path = str(hosts_file)
    return mgr


class TestInit:
    def test_paths_set(self, cfg, agent_dir):
        assert cfg.dir_root == str(agent_dir)
        assert cfg.is_64bit is False
        assert cfg.failclose_active is False
        assert cfg.exception_names == []
        assert cfg.gateway_hosts == []


class TestCheckWatchdogMode:
    def test_true_bool(self, cfg):
        data = {"clientConfig": {"nsclient_watchdog_monitor": True}}
        ns = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(ns, "w", encoding="utf-8") as f:
            json.dump(data, f)
        assert cfg.check_watchdog_mode() is True

    def test_true_string(self, cfg):
        data = {"clientConfig": {"nsclient_watchdog_monitor": "true"}}
        ns = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(ns, "w", encoding="utf-8") as f:
            json.dump(data, f)
        assert cfg.check_watchdog_mode() is True

    def test_false(self, cfg):
        data = {"clientConfig": {"nsclient_watchdog_monitor": False}}
        ns = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(ns, "w", encoding="utf-8") as f:
            json.dump(data, f)
        assert cfg.check_watchdog_mode() is False

    def test_missing_file(self, cfg):
        assert cfg.check_watchdog_mode() is False

    def test_missing_key(self, cfg):
        ns = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(ns, "w", encoding="utf-8") as f:
            json.dump({"clientConfig": {}}, f)
        assert cfg.check_watchdog_mode() is False


class TestLoadNsexception:
    def test_loads_dict_format(self, cfg):
        data = {"names": ["*.example.com", "test.org"]}
        with open(cfg.exception_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        cfg.load_nsexception()
        assert len(cfg.exception_names) == 2
        assert "*.example.com" in cfg.exception_names

    def test_loads_list_format(self, cfg):
        data = [
            {"names": ["a.com", "b.com"]},
            {"names": ["c.com"]},
        ]
        with open(cfg.exception_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        cfg.load_nsexception()
        assert len(cfg.exception_names) == 3

    def test_missing_file(self, cfg):
        cfg.load_nsexception()
        assert cfg.exception_names == []

    def test_invalid_json(self, cfg):
        with open(cfg.exception_path, "w", encoding="utf-8") as f:
            f.write("{bad")
        cfg.load_nsexception()
        assert cfg.exception_names == []


class TestUrlInNsexception:
    def test_wildcard_match(self, cfg):
        cfg.exception_names = ["*.example.com"]
        assert cfg.url_in_nsexception("https://sub.example.com/page") is True

    def test_exact_match(self, cfg):
        cfg.exception_names = ["example.com"]
        assert cfg.url_in_nsexception("https://example.com") is True

    def test_subdomain_match(self, cfg):
        cfg.exception_names = ["example.com"]
        assert cfg.url_in_nsexception("https://sub.example.com") is True

    def test_wildcard_bare_domain(self, cfg):
        cfg.exception_names = ["*.example.com"]
        assert cfg.url_in_nsexception("https://example.com") is True

    def test_no_match(self, cfg):
        cfg.exception_names = ["other.com"]
        assert cfg.url_in_nsexception("https://example.com") is False

    def test_empty_url(self, cfg):
        cfg.exception_names = ["example.com"]
        assert cfg.url_in_nsexception("") is False

    def test_empty_exceptions(self, cfg):
        cfg.exception_names = []
        assert cfg.url_in_nsexception("https://example.com") is False


class TestGetTenantHostname:
    def test_extracts_hostname(self, cfg):
        data = {"nsgw": {"host": "gateway-tenant.example.com"}}
        ns = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(ns, "w", encoding="utf-8") as f:
            json.dump(data, f)
        assert cfg.get_tenant_hostname() == "tenant.example.com"

    def test_no_gateway_prefix(self, cfg):
        data = {"nsgw": {"host": "something.example.com"}}
        ns = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(ns, "w", encoding="utf-8") as f:
            json.dump(data, f)
        assert cfg.get_tenant_hostname() == ""

    def test_missing_file(self, cfg):
        assert cfg.get_tenant_hostname() == ""

    def test_empty_host(self, cfg):
        data = {"nsgw": {"host": ""}}
        ns = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(ns, "w", encoding="utf-8") as f:
            json.dump(data, f)
        assert cfg.get_tenant_hostname() == ""


class TestSetupEnvironment:
    @patch("util_config.sys.platform", "win32")
    @patch("util_config.os.path.exists")
    @patch("platforms.windows.service.WindowsServiceManager")
    def test_returns_false_when_service_missing(
        self, mock_svc_cls, mock_exists, cfg
    ):
        mock_svc = MagicMock()
        mock_svc.get_service_status.return_value = "NOT_FOUND"
        mock_svc_cls.return_value = mock_svc

        def _exists(path):
            if path == cfg.hosts_path:
                return False
            if path == cfg.target_nsconfig:
                return False
            return False

        mock_exists.side_effect = _exists

        ok = cfg.setup_environment()

        assert ok is False
        assert "Client not installed" in cfg.last_setup_error


class TestModifyHostsFileEntries:
    def test_add_entries(self, cfg, hosts_file):
        entries = [("10.1.1.1", "blocked.com")]
        cfg.modify_hosts_file_entries(entries, add_entries=True)
        content = hosts_file.read_text(encoding="utf-8")
        assert "10.1.1.1 blocked.com" in content
        assert "127.0.0.1 localhost" in content

    def test_remove_entries(self, cfg, hosts_file):
        hosts_file.write_text(
            "127.0.0.1 localhost\n10.1.1.1 blocked.com\n",
            encoding="utf-8",
        )
        entries = [("10.1.1.1", "blocked.com")]
        cfg.modify_hosts_file_entries(entries, add_entries=False)
        content = hosts_file.read_text(encoding="utf-8")
        assert "blocked.com" not in content
        assert "localhost" in content

    def test_add_replaces_existing(self, cfg, hosts_file):
        hosts_file.write_text(
            "127.0.0.1 localhost\n10.0.0.1 myhost.com\n",
            encoding="utf-8",
        )
        entries = [("10.1.1.1", "myhost.com")]
        cfg.modify_hosts_file_entries(entries, add_entries=True)
        content = hosts_file.read_text(encoding="utf-8")
        lines = [l for l in content.splitlines() if "myhost.com" in l]
        assert len(lines) == 1
        assert "10.1.1.1" in lines[0]


class TestRestoreConfig:
    def test_restores_backup(self, cfg, tmp_path):
        backup = tmp_path / "data" / "nsconfig-bk.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text('{"restored": true}', encoding="utf-8")
        cfg.backup_path = str(backup)

        target = os.path.join(cfg.stagent_root, "nsconfig.json")
        cfg.target_nsconfig = target

        cfg.hosts_bk = str(tmp_path / "hosts-bk")
        cfg.restore_config()
        assert not backup.exists()
        assert os.path.exists(target)
        with open(target, "r", encoding="utf-8") as f:
            assert json.load(f) == {"restored": True}

    def test_remove_only(self, cfg, tmp_path):
        backup = tmp_path / "data" / "nsconfig-bk.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text("{}", encoding="utf-8")
        cfg.backup_path = str(backup)
        cfg.hosts_bk = str(tmp_path / "hosts-bk-none")
        cfg.restore_config(remove_only=True)
        assert not backup.exists()

    def test_no_backup(self, cfg, tmp_path):
        cfg.backup_path = str(tmp_path / "nonexistent.json")
        cfg.hosts_bk = str(tmp_path / "hosts-bk-none")
        cfg.restore_config()


class TestToggleFailclose:
    def test_activate(self, cfg, hosts_file, tmp_path):
        cfg.gateway_hosts = ["gw.example.com"]
        cfg.failclose_active = False
        cfg.hosts_bk = str(tmp_path / "hosts-bk")
        cfg.backup_path = str(tmp_path / "nsconfig-bk.json")

        nsconfig = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(nsconfig, "w", encoding="utf-8") as f:
            json.dump({"nsgw": {}}, f)

        cfg.toggle_failclose()
        assert cfg.failclose_active is True
        content = hosts_file.read_text(encoding="utf-8")
        assert "gw.example.com" in content

    def test_deactivate(self, cfg, hosts_file):
        cfg.gateway_hosts = ["gw.example.com"]
        cfg.failclose_active = True
        hosts_file.write_text(
            "127.0.0.1 localhost\n10.1.1.1 gw.example.com\n",
            encoding="utf-8",
        )
        nsconfig = os.path.join(cfg.stagent_root, "nsconfig.json")
        with open(nsconfig, "w", encoding="utf-8") as f:
            json.dump({"failClose": {"fail_close": "true"}}, f)

        cfg.toggle_failclose()
        assert cfg.failclose_active is False
        content = hosts_file.read_text(encoding="utf-8")
        assert "gw.example.com" not in content

    def test_no_gateway_hosts(self, cfg):
        cfg.gateway_hosts = []
        cfg.failclose_active = False
        cfg.toggle_failclose()
        assert cfg.failclose_active is False


class TestToggleOnOffPrem:
    def test_odd_iteration_adds_entry(self, cfg, hosts_file):
        result = cfg.toggle_on_off_prem("http://host.test.com", 1)
        assert result is True
        content = hosts_file.read_text(encoding="utf-8")
        assert "host.test.com" in content

    def test_even_iteration_removes_entry(self, cfg, hosts_file):
        hosts_file.write_text(
            "127.0.0.1 localhost\n10.1.1.1 host.test.com\n",
            encoding="utf-8",
        )
        result = cfg.toggle_on_off_prem("http://host.test.com", 2)
        assert result is True
        content = hosts_file.read_text(encoding="utf-8")
        assert "host.test.com" not in content

    def test_plain_hostname(self, cfg, hosts_file):
        result = cfg.toggle_on_off_prem("plainhost.com", 1)
        assert result is True
        content = hosts_file.read_text(encoding="utf-8")
        assert "plainhost.com" in content
