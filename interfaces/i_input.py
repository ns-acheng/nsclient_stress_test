from abc import ABC, abstractmethod
import threading

class IInputMonitor(ABC):
    @abstractmethod
    def start_input_monitor(self, stop_event: threading.Event) -> None:
        pass

    @abstractmethod
    def stop_input_monitor(self) -> None:
        pass
