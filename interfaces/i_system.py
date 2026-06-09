from abc import ABC, abstractmethod

class ISystemInfo(ABC):
    @abstractmethod
    def get_memory_usage(self) -> tuple[int, int]:
        """Returns (percent_usage, available_mb)"""
        pass

    @abstractmethod
    def enable_privilege(self, privilege_name: str) -> int:
        pass
    
    @abstractmethod
    def log_process_usage(self, process_name: str, log_dir: str) -> bool:
        pass

    @abstractmethod
    def set_startup_task(self, task_name: str, command: str) -> bool:
        pass

    @abstractmethod
    def get_process_pid(self, process_name: str) -> int:
        pass

    @abstractmethod
    def run_shell_script(self, script_path: str, args: list = None) -> None:
        pass
