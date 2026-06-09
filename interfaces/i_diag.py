from abc import ABC, abstractmethod

class IDiagnostics(ABC):
    @abstractmethod
    def check_crash_dumps(self, custom_dump_path: str = "") -> tuple[bool, int]:
        pass

    @abstractmethod
    def collect_log_bundle(self, timestamp: str, is_64bit: bool, output_dir: str) -> None:
        pass

    @abstractmethod
    def sync_client_config(self, is_64bit: bool) -> None:
        pass

    @abstractmethod
    def enable_client_tracing(self, enable: bool, is_64bit: bool) -> None:
        pass

    @abstractmethod
    def handle_crash(self, is_64bit: bool, log_dir: str, custom_dump_path: str = "") -> None:
        pass

    @abstractmethod
    def generate_live_dump(self, pid: int, output_dir: str) -> None:
        pass
