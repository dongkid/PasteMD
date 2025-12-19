import platform


def get_os_name() -> str:
    sys_name = platform.system().lower()
    if sys_name == "darwin":
        return "macos"
    if sys_name == "windows":
        return "windows"
    if sys_name == "linux":
        return "linux"
    return "unknown"


def is_macos() -> bool:
    return get_os_name() == "macos"


def is_windows() -> bool:
    return get_os_name() == "windows"


def is_linux() -> bool:
    return get_os_name() == "linux"
