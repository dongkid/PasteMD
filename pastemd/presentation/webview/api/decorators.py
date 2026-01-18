"""API decorators for WebView."""

from functools import wraps
from typing import Callable, TypeVar, ParamSpec

from ....utils.system_detect import is_macos

P = ParamSpec("P")
R = TypeVar("R")


def macos_only(func: Callable[P, R]) -> Callable[P, R]:
    """
    限制方法仅在 macOS 上执行

    在非 macOS 平台上调用时，返回 PLATFORM_ERROR 错误响应。
    """
    @wraps(func)
    def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if not is_macos():
            return self._error("Not macOS", "PLATFORM_ERROR")
        return func(self, *args, **kwargs)
    return wrapper
