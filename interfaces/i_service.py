from abc import ABC, abstractmethod

class IServiceManager(ABC):
    @abstractmethod
    def start_service(self, service_name: str) -> bool:
        pass

    @abstractmethod
    def stop_service(self, service_name: str, timeout: int = 30) -> bool:
        pass

    @abstractmethod
    def get_service_status(self, service_name: str) -> str:
        pass

    @abstractmethod
    def handle_non_stop(self, service_name: str, is_64bit: bool, log_dir: str) -> None:
        pass
