from abc import ABC, abstractmethod

class IPowerManager(ABC):
    @abstractmethod
    def enter_s0_and_wake(self, duration_seconds: int) -> bool:
        pass

    @abstractmethod
    def enter_s1_and_wake(self, duration_seconds: int) -> bool:
        pass

    @abstractmethod
    def enter_s4_and_wake(self, duration_seconds: int) -> bool:
        pass

    @abstractmethod
    def is_sleep_state_available(self, state_name: str) -> bool:
        pass

    @abstractmethod
    def reboot(self) -> None:
        pass

    @abstractmethod
    def enable_wake_timers(self) -> bool:
        pass
