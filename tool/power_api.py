import platform

from interfaces.i_power import IPowerManager


def get_power_manager(system_name: str | None = None) -> IPowerManager:
    system = (system_name or platform.system()).lower()
    if system == "windows":
        from platforms.windows.factory import WindowsFactory

        return WindowsFactory().create_power_manager()
    if system == "darwin":
        from platforms.macos.factory import MacOSFactory

        return MacOSFactory().create_power_manager()
    raise NotImplementedError(f"OS {system} not supported")


def enter_s0_and_wake(
    duration_seconds: int,
    power_manager: IPowerManager | None = None,
) -> bool:
    manager = power_manager or get_power_manager()
    return manager.enter_s0_and_wake(duration_seconds)


def enter_s1_and_wake(
    duration_seconds: int,
    power_manager: IPowerManager | None = None,
) -> bool:
    manager = power_manager or get_power_manager()
    return manager.enter_s1_and_wake(duration_seconds)


__all__ = [
    "get_power_manager",
    "enter_s0_and_wake",
    "enter_s1_and_wake",
]
