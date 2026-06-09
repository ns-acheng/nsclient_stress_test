from interfaces.i_factory import IPlatformFactory
# Interfaces
from interfaces.i_power import IPowerManager
from interfaces.i_service import IServiceManager
from interfaces.i_system import ISystemInfo
from interfaces.i_input import IInputMonitor
from interfaces.i_diag import IDiagnostics

# Implementations
from platforms.macos.power import MacOSPowerManager
from platforms.macos.service import MacOSServiceManager
from platforms.macos.system import MacOSSystemInfo
from platforms.macos.input import MacOSInputMonitor
from platforms.macos.diag import MacOSDiagnostics
from platforms.macos.env import MacOSEnvironment
from interfaces.i_env import IEnvironment

class MacOSFactory(IPlatformFactory):
    def create_power_manager(self) -> IPowerManager:
        return MacOSPowerManager()

    def create_service_manager(self) -> IServiceManager:
        return MacOSServiceManager()

    def create_system_info(self) -> ISystemInfo:
        return MacOSSystemInfo()

    def create_input_monitor(self) -> IInputMonitor:
        return MacOSInputMonitor()

    def create_diagnostics(self) -> IDiagnostics:
        return MacOSDiagnostics()

    def create_environment(self) -> IEnvironment:
        return MacOSEnvironment()
