from interfaces.i_factory import IPlatformFactory
from interfaces.i_power import IPowerManager
from interfaces.i_service import IServiceManager
from interfaces.i_system import ISystemInfo
from interfaces.i_input import IInputMonitor
from interfaces.i_diag import IDiagnostics
from interfaces.i_env import IEnvironment

from platforms.linux.power import LinuxPowerManager
from platforms.linux.service import LinuxServiceManager
from platforms.linux.system import LinuxSystemInfo
from platforms.linux.input import LinuxInputMonitor
from platforms.linux.diag import LinuxDiagnostics
from platforms.linux.env import LinuxEnvironment

class LinuxFactory(IPlatformFactory):
    """Factory for creating Linux platform-specific implementations."""

    def create_power_manager(self) -> IPowerManager:
        return LinuxPowerManager()

    def create_service_manager(self) -> IServiceManager:
        return LinuxServiceManager()

    def create_system_info(self) -> ISystemInfo:
        return LinuxSystemInfo()

    def create_input_monitor(self) -> IInputMonitor:
        return LinuxInputMonitor()

    def create_diagnostics(self) -> IDiagnostics:
        return LinuxDiagnostics()

    def create_environment(self) -> IEnvironment:
        return LinuxEnvironment()
