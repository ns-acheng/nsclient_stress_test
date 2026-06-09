from abc import ABC, abstractmethod

class IEnvironment(ABC):
    @property
    @abstractmethod
    def agent_data_dir(self) -> str:
        pass

    @property
    @abstractmethod
    def agent_log_file(self) -> str:
        pass

    @property
    @abstractmethod
    def system_hosts_file(self) -> str:
        pass
