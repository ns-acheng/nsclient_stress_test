from unittest.mock import patch, MagicMock

import pytest

from interfaces.i_factory import IPlatformFactory
from interfaces.i_power import IPowerManager
from interfaces.i_service import IServiceManager
from interfaces.i_system import ISystemInfo
from interfaces.i_input import IInputMonitor
from interfaces.i_diag import IDiagnostics
from interfaces.i_env import IEnvironment


class TestIPlatformFactoryABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            IPlatformFactory()

    def test_concrete_factory_creates_all(self):
        class FakeFactory(IPlatformFactory):
            def create_power_manager(self):
                return MagicMock(spec=IPowerManager)

            def create_service_manager(self):
                return MagicMock(spec=IServiceManager)

            def create_system_info(self):
                return MagicMock(spec=ISystemInfo)

            def create_input_monitor(self):
                return MagicMock(spec=IInputMonitor)

            def create_diagnostics(self):
                return MagicMock(spec=IDiagnostics)

            def create_environment(self):
                return MagicMock(spec=IEnvironment)

        f = FakeFactory()
        assert isinstance(f.create_power_manager(), IPowerManager)
        assert isinstance(f.create_service_manager(), IServiceManager)
        assert isinstance(f.create_system_info(), ISystemInfo)
        assert isinstance(f.create_input_monitor(), IInputMonitor)
        assert isinstance(f.create_diagnostics(), IDiagnostics)
        assert isinstance(f.create_environment(), IEnvironment)


class TestWindowsFactory:
    def test_creates_all_components(self):
        with patch(
            "platforms.windows.power.WindowsPowerManager"
        ), patch(
            "platforms.windows.service.WindowsServiceManager"
        ), patch(
            "platforms.windows.system.WindowsSystemInfo"
        ), patch(
            "platforms.windows.input.WindowsInputMonitor"
        ), patch(
            "platforms.windows.diag.WindowsDiagnostics"
        ), patch(
            "platforms.windows.env.WindowsEnvironment"
        ):
            from platforms.windows.factory import WindowsFactory
            f = WindowsFactory()
            assert f.create_power_manager() is not None
            assert f.create_service_manager() is not None
            assert f.create_system_info() is not None
            assert f.create_input_monitor() is not None
            assert f.create_diagnostics() is not None
            assert f.create_environment() is not None
