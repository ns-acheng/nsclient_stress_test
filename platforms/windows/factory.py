from interfaces.i_factory import IPlatformFactory
from interfaces.i_power import IPowerManager
from interfaces.i_service import IServiceManager
from interfaces.i_system import ISystemInfo
from interfaces.i_input import IInputMonitor
from interfaces.i_diag import IDiagnostics
from interfaces.i_env import IEnvironment

from platforms.windows.power import WindowsPowerManager
from platforms.windows.service import WindowsServiceManager
from platforms.windows.system import WindowsSystemInfo
from platforms.windows.input import WindowsInputMonitor
from platforms.windows.diag import WindowsDiagnostics
from platforms.windows.env import WindowsEnvironment

class WindowsFactory(IPlatformFactory):
    def create_power_manager(self) -> IPowerManager:
        return WindowsPowerManager()

    def create_service_manager(self) -> IServiceManager:
        return WindowsServiceManager()

    def create_system_info(self) -> ISystemInfo:
        return WindowsSystemInfo()

    def create_input_monitor(self) -> IInputMonitor:
        return WindowsInputMonitor()

    def create_diagnostics(self) -> IDiagnostics:
        return WindowsDiagnostics()

    def create_environment(self) -> IEnvironment:
        return WindowsEnvironment()
