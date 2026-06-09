from unittest.mock import MagicMock, patch

import pytest

import util_webui


@pytest.fixture(autouse=True)
def _mock_webapi_imports(monkeypatch):
    monkeypatch.setattr(util_webui, "WebAPI", MagicMock(), raising=False)
    monkeypatch.setattr(
        util_webui, "Authentication", MagicMock(), raising=False
    )
    monkeypatch.setattr(
        util_webui, "ClientConfiguration", MagicMock(), raising=False
    )
    monkeypatch.setattr(
        util_webui, "SteeringConfiguration", MagicMock(), raising=False
    )


class TestWebUIClientInit:
    def test_stores_credentials(self):
        c = util_webui.WebUIClient("host.com", "user", "pass")
        assert c.hostname == "host.com"
        assert c.username == "user"
        assert c.password == "pass"
        assert c.is_logged_in is False
        assert c.client_config_name == "Default tenant config"
        assert c.steering_config_name == "Default tenant config"

    def test_raises_when_webapi_missing(self, monkeypatch):
        monkeypatch.setattr(util_webui, "WebAPI", None)
        with pytest.raises(ImportError):
            util_webui.WebUIClient("host.com", "user", "pass")


class TestWebUIClientLogin:
    def test_login_success(self):
        with patch.object(util_webui, "WebAPI") as mock_wa, \
             patch.object(util_webui, "Authentication") as mock_auth:
            client = util_webui.WebUIClient("h", "u", "p")
            assert client.login() is True
            assert client.is_logged_in is True
            mock_auth.return_value.login.assert_called_once()

    def test_login_failure(self):
        with patch.object(util_webui, "WebAPI") as mock_wa, \
             patch.object(util_webui, "Authentication") as mock_auth:
            mock_auth.return_value.login.side_effect = Exception("fail")
            client = util_webui.WebUIClient("h", "u", "p")
            assert client.login() is False
            assert client.is_logged_in is False


class TestUpdateClientConfig:
    def test_success(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.update_client_config(
                onpremcheck=1
            ) is True

    def test_failure_response(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "error"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.update_client_config(
                onpremcheck=1
            ) is False

    def test_auto_login_on_not_logged_in(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            assert client.update_client_config(
                onpremcheck=1
            ) is True
            assert client.is_logged_in is True

    def test_exception_returns_false(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.side_effect = (
                Exception("boom")
            )
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.update_client_config(
                onpremcheck=1
            ) is False


class TestUpdateSteeringConfig:
    def test_update_traffic_mode(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.update_steering_config(
                traffic_mode="all"
            ) is True
            mock_sc.return_value \
                .update_traffic_steering_mode \
                .assert_called_once()

    def test_add_exception_domains(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.update_steering_config(
                exception_domains=["ex.com"]
            ) is True
            mock_sc.return_value \
                .add_exception_domains \
                .assert_called_once()

    def test_exception_returns_false(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            mock_sc.side_effect = Exception("err")
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.update_steering_config(
                traffic_mode="web"
            ) is False


class TestToggleTlsDtls:
    def test_toggle_to_dtls(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_tls_dtls(use_dtls=True) is True
            mock_cc.return_value.update_client_config.assert_called_once()

    def test_toggle_to_tls(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_tls_dtls(use_dtls=False) is True
            mock_cc.return_value.update_client_config.assert_called_once()

    def test_uses_loaded_config_name(self, tmp_path):
        stagent = tmp_path / "stagent"
        stagent.mkdir()
        (stagent / "nsconfig.json").write_text(
            '{"clientConfig":{"configurationName":"Custom CC"}}',
            encoding="utf-8"
        )
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.load_config_names_from_local(str(stagent))
            client.login()
            assert client.toggle_tls_dtls(use_dtls=True) is True
            call_kwargs = (
                mock_cc.return_value.update_client_config.call_args
            )
            assert call_kwargs.kwargs["search_config"] == "Custom CC"

    def test_toggle_failure(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "error"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_tls_dtls(use_dtls=True) is False

    def test_toggle_exception(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.side_effect = (
                Exception("boom")
            )
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_tls_dtls(use_dtls=True) is False


class TestLoadConfigNamesFromLocal:
    def test_reads_both_files(self, tmp_path):
        stagent = tmp_path / "stagent"
        stagent.mkdir()
        (stagent / "nsconfig.json").write_text(
            '{"clientConfig":{"configurationName":"My CC"}}',
            encoding="utf-8"
        )
        data_dir = stagent / "data"
        data_dir.mkdir()
        (data_dir / "nssteering.json").write_text(
            '{"steering_config_name":"My SC"}',
            encoding="utf-8"
        )
        client = util_webui.WebUIClient("h", "u", "p")
        client.load_config_names_from_local(str(stagent))
        assert client.client_config_name == "My CC"
        assert client.steering_config_name == "My SC"

    def test_keeps_defaults_when_files_missing(self, tmp_path):
        client = util_webui.WebUIClient("h", "u", "p")
        client.load_config_names_from_local(str(tmp_path / "nonexistent"))
        assert client.client_config_name == "Default tenant config"
        assert client.steering_config_name == "Default tenant config"

    def test_keeps_defaults_when_keys_missing(self, tmp_path):
        stagent = tmp_path / "stagent"
        stagent.mkdir()
        (stagent / "nsconfig.json").write_text(
            '{"clientConfig":{}}', encoding="utf-8"
        )
        data_dir = stagent / "data"
        data_dir.mkdir()
        (data_dir / "nssteering.json").write_text(
            '{}', encoding="utf-8"
        )
        client = util_webui.WebUIClient("h", "u", "p")
        client.load_config_names_from_local(str(stagent))
        assert client.client_config_name == "Default tenant config"
        assert client.steering_config_name == "Default tenant config"


class TestToggleSteeringMode:
    def test_toggle_to_all(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_steering_mode(use_all=True) is True
            mock_sc.return_value \
                .update_traffic_steering_mode \
                .assert_called_once()

    def test_toggle_to_web(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_steering_mode(use_all=False) is True

    def test_toggle_exception(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            mock_sc.side_effect = Exception("err")
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_steering_mode(use_all=True) is False


class TestToggleWebuiFailclose:
    def test_enable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_webui_failclose(enable=True) is True
            mock_cc.return_value.update_client_config.assert_called_once_with(
                search_config="Default tenant config",
                failClose=1
            )

    def test_disable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_webui_failclose(enable=False) is True
            mock_cc.return_value.update_client_config.assert_called_once_with(
                search_config="Default tenant config",
                failClose=0
            )

    def test_failure(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "error"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_webui_failclose(enable=True) is False


class TestToggleSniCheck:
    def test_enable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_sni_check(enable=True) is True
            mock_cc.return_value.update_client_config.assert_called_once_with(
                search_config="Default tenant config",
                checkSNI="true"
            )

    def test_disable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_sni_check(enable=False) is True
            mock_cc.return_value.update_client_config.assert_called_once_with(
                search_config="Default tenant config",
                checkSNI="false"
            )

    def test_exception(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.side_effect = (
                Exception("boom")
            )
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_sni_check(enable=True) is False


class TestToggleExceptionDomains:
    def test_add_domains(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_exception_domains(
                add=True, domains=["a.com", "b.com"]
            ) is True
            mock_sc.return_value \
                .add_exception_domains \
                .assert_called_once()

    def test_remove_domains(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_exception_domains(
                add=False, domains=["a.com"]
            ) is True
            mock_sc.return_value \
                .remove_exception_domains \
                .assert_called_once()

    def test_empty_domains_returns_false(self):
        client = util_webui.WebUIClient("h", "u", "p")
        assert client.toggle_exception_domains(
            add=True, domains=[]
        ) is False

    def test_exception_returns_false(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            mock_sc.side_effect = Exception("err")
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_exception_domains(
                add=True, domains=["a.com"]
            ) is False

    def test_uses_steering_config_name(self, tmp_path):
        stagent = tmp_path / "stagent"
        stagent.mkdir()
        data_dir = stagent / "data"
        data_dir.mkdir()
        (data_dir / "nssteering.json").write_text(
            '{"steering_config_name":"Custom SC"}',
            encoding="utf-8"
        )
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.load_config_names_from_local(str(stagent))
            client.login()
            client.toggle_exception_domains(
                add=True, domains=["x.com"]
            )
            call_kwargs = (
                mock_sc.return_value
                .add_exception_domains.call_args
            )
            assert call_kwargs.kwargs["config_name"] == "Custom SC"


class TestToggleClientDisabling:
    def test_enable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_client_disabling(enable=True) is True
            mock_cc.return_value.update_client_config.assert_called_once_with(
                search_config="Default tenant config",
                allowClientDisabling=1
            )

    def test_disable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_client_disabling(enable=False) is True
            mock_cc.return_value.update_client_config.assert_called_once_with(
                search_config="Default tenant config",
                allowClientDisabling=0
            )

    def test_failure(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "error"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_client_disabling(enable=True) is False

    def test_exception(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.side_effect = (
                Exception("boom")
            )
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_client_disabling(enable=True) is False


class TestToggleCustomPorts:
    def test_add_ports(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            ports = [{"ports": "9501", "domains": "test.com",
                      "description": "test"}]
            assert client.toggle_custom_ports(
                add=True, ports=ports
            ) is True
            mock_sc.return_value \
                .add_custom_ports \
                .assert_called_once()

    def test_remove_ports(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            ports = [{"ports": "9501", "domains": "test.com",
                      "description": "test"}]
            assert client.toggle_custom_ports(
                add=False, ports=ports
            ) is True
            mock_sc.return_value \
                .delete_custom_ports \
                .assert_called_once()

    def test_empty_ports_returns_false(self):
        client = util_webui.WebUIClient("h", "u", "p")
        assert client.toggle_custom_ports(
            add=True, ports=[]
        ) is False

    def test_exception_returns_false(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "SteeringConfiguration"
             ) as mock_sc:
            mock_sc.side_effect = Exception("err")
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_custom_ports(
                add=True,
                ports=[{"ports": "9501"}]
            ) is False


class TestToggleInteropProxy:
    def test_enable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_interop_proxy(
                enable=True, host="proxy.com", port=8080
            ) is True
            call_kw = (
                mock_cc.return_value
                .update_client_config.call_args.kwargs
            )
            assert call_kw["interopProxy"] == 1
            assert call_kw["interopProxy_host"] == "proxy.com"
            assert call_kw["interopProxy_port"] == 8080

    def test_disable(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_interop_proxy(
                enable=False
            ) is True
            call_kw = (
                mock_cc.return_value
                .update_client_config.call_args.kwargs
            )
            assert call_kw["interopProxy"] == 0
            assert "interopProxy_host" not in call_kw

    def test_failure(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "error"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.toggle_interop_proxy(
                enable=True
            ) is False


class TestSetMtu:
    def test_set_value(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.set_mtu(1200) is True
            call_kw = (
                mock_cc.return_value
                .update_client_config.call_args.kwargs
            )
            assert call_kw["mtu"] == 1200

    def test_set_empty(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "success"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.set_mtu("") is True

    def test_failure(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.return_value = {
                "status": "error"
            }
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.set_mtu(800) is False

    def test_exception(self):
        with patch.object(util_webui, "WebAPI"), \
             patch.object(util_webui, "Authentication"), \
             patch.object(
                 util_webui, "ClientConfiguration"
             ) as mock_cc:
            mock_cc.return_value.update_client_config.side_effect = (
                Exception("boom")
            )
            client = util_webui.WebUIClient("h", "u", "p")
            client.login()
            assert client.set_mtu(800) is False


class TestPerformOnpremSetup:
    def _base_config(self):
        return {
            "client_feature_toggling": {
                "webui_on_prem": {
                    "enable": 1,
                    "onprem_use_dns": 0,
                    "onprem_http_host": "http://api.local",
                },
                "webui_login": {
                    "tenant_hostname": "host.com",
                    "tenant_username": "user@test.com",
                },
            }
        }

    def test_success(self):
        cfg = self._base_config()
        with patch("util_webui.WebUIClient") as mock_cls:
            inst = mock_cls.return_value
            inst.login.return_value = True
            assert util_webui.perform_onprem_setup(
                cfg, "fallback.com", "pw"
            ) is True
            inst.update_client_config.assert_called_once()

    def test_disabled_returns_false(self):
        cfg = self._base_config()
        cfg["client_feature_toggling"]["webui_on_prem"]["enable"] = 0
        assert util_webui.perform_onprem_setup(
            cfg, "h", "pw"
        ) is False

    def test_missing_username_returns_false(self):
        cfg = self._base_config()
        cfg["client_feature_toggling"]["webui_login"][
            "tenant_username"
        ] = ""
        assert util_webui.perform_onprem_setup(
            cfg, "h", "pw"
        ) is False

    def test_login_failure_returns_false(self):
        cfg = self._base_config()
        with patch("util_webui.WebUIClient") as mock_cls:
            inst = mock_cls.return_value
            inst.login.return_value = False
            assert util_webui.perform_onprem_setup(
                cfg, "h", "pw"
            ) is False
