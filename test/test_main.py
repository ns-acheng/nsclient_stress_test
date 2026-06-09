import sys
from unittest.mock import MagicMock, patch, call

import pytest

import main as main_mod


class TestGetFactory:
    def test_returns_windows_factory_on_windows(self):
        with patch.object(main_mod.platform, "system", return_value="Windows"):
            with patch(
                "platforms.windows.factory.WindowsFactory"
            ) as mock_cls:
                factory = main_mod.get_factory()
                mock_cls.assert_called_once()

    def test_returns_macos_factory_on_darwin(self):
        mock_cls = MagicMock()
        mock_module = MagicMock()
        mock_module.MacOSFactory = mock_cls
        with patch.object(main_mod.platform, "system", return_value="Darwin"):
            with patch.dict(
                sys.modules,
                {"platforms.macos.factory": mock_module},
            ):
                factory = main_mod.get_factory()
                mock_cls.assert_called_once()

    def test_raises_on_unsupported_os(self):
        with patch.object(
            main_mod.platform, "system", return_value="FreeBSD"
        ):
            with pytest.raises(NotImplementedError):
                main_mod.get_factory()


class TestMain:
    @pytest.fixture
    def _mock_all(self, tmp_path):
        mock_factory = MagicMock()
        mock_log_setup = MagicMock()
        mock_log_setup.return_value.get_log_folder.return_value = str(
            tmp_path / "logs"
        )
        mock_runner = MagicMock()

        patches = {
            "factory": patch.object(
                main_mod, "get_factory", return_value=mock_factory
            ),
            "log": patch.object(
                main_mod, "LogSetup", mock_log_setup
            ),
            "stress": patch.object(
                main_mod, "StressTest", return_value=mock_runner
            ),
            "validator": patch.object(
                main_mod, "init_validator"
            ),
            "config_mgr": patch.object(
                main_mod, "AgentConfigManager",
                return_value=MagicMock(),
            ),
            "chdir": patch.object(main_mod.os, "chdir"),
            "copy": patch.object(main_mod.shutil, "copy"),
            "exists": patch.object(
                main_mod.os.path, "exists", return_value=True
            ),
            "argv": patch.object(main_mod.sys, "argv", ["main.py"]),
            "exit": patch.object(main_mod.sys, "exit"),
        }

        started = {k: p.start() for k, p in patches.items()}
        yield {
            "factory": mock_factory,
            "log_setup": mock_log_setup,
            "runner": mock_runner,
            **started,
        }
        for p in patches.values():
            p.stop()

    def test_normal_run(self, _mock_all):
        main_mod.main()
        _mock_all["runner"].setup.assert_called_once()
        _mock_all["runner"].run.assert_called_once()
        _mock_all["runner"].tear_down.assert_called_once()

    def test_keyboard_interrupt(self, _mock_all):
        _mock_all["runner"].run.side_effect = KeyboardInterrupt
        main_mod.main()
        _mock_all["runner"].tear_down.assert_called_once()

    def test_continue_mode(self, _mock_all, tmp_path):
        state_file = tmp_path / "data" / "state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            '{"cur_log_dir": "log/prev"}', encoding="utf-8"
        )

        with patch.object(main_mod.sys, "argv", ["main.py", "-continue"]):
            with patch(
                "builtins.open",
                create=True,
            ) as mock_open:
                import io, json
                mock_open.return_value.__enter__ = lambda s: io.StringIO(
                    json.dumps({"cur_log_dir": "log/prev"})
                )
                mock_open.return_value.__exit__ = (
                    lambda s, *a: None
                )
                main_mod.main()

        _mock_all["runner"].setup.assert_called_once()

    def test_skips_run_when_setup_returns_false(self, _mock_all):
        _mock_all["runner"].setup.return_value = False
        main_mod.main()
        _mock_all["runner"].setup.assert_called_once()
        _mock_all["runner"].run.assert_not_called()
        _mock_all["runner"].tear_down.assert_called_once()
