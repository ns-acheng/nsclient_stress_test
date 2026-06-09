from abc import ABC, abstractmethod
from interfaces.i_power import IPowerManager
from interfaces.i_service import IServiceManager
from interfaces.i_system import ISystemInfo
from interfaces.i_input import IInputMonitor
from interfaces.i_diag import IDiagnostics
from interfaces.i_env import IEnvironment

class IPlatformFactory(ABC):
    @abstractmethod
    def create_power_manager(self) -> IPowerManager:
        pass

    @abstractmethod
    def create_service_manager(self) -> IServiceManager:
        pass

    @abstractmethod
    def create_system_info(self) -> ISystemInfo:
        pass

    @abstractmethod
    def create_input_monitor(self) -> IInputMonitor:
        pass

    @abstractmethod
    def create_diagnostics(self) -> IDiagnostics:
        pass

    @abstractmethod
    def create_environment(self) -> IEnvironment:
        pass
