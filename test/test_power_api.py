from unittest.mock import MagicMock, patch

from tool import power_api


class TestGetPowerManager:
    def test_returns_windows_power_manager_on_windows(self):
        expected = MagicMock()
        factory = MagicMock()
        factory.create_power_manager.return_value = expected

        with patch.object(power_api.platform, "system", return_value="Windows"):
            with patch("platforms.windows.factory.WindowsFactory", return_value=factory):
                result = power_api.get_power_manager()

        assert result is expected

    def test_raises_on_unsupported_os(self):
        with patch.object(power_api.platform, "system", return_value="FreeBSD"):
            try:
                power_api.get_power_manager()
                assert False, "Expected NotImplementedError"
            except NotImplementedError:
                assert True


class TestExportedPowerApis:
    def test_enter_s0_and_wake_delegates(self):
        manager = MagicMock()
        manager.enter_s0_and_wake.return_value = True

        result = power_api.enter_s0_and_wake(30, power_manager=manager)

        assert result is True
        manager.enter_s0_and_wake.assert_called_once_with(30)

    def test_enter_s1_and_wake_delegates(self):
        manager = MagicMock()
        manager.enter_s1_and_wake.return_value = True

        result = power_api.enter_s1_and_wake(45, power_manager=manager)

        assert result is True
        manager.enter_s1_and_wake.assert_called_once_with(45)
