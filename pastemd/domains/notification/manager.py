# notification_manager.py
"""Notification manager: Win11/Win10 toast with async worker (non-blocking)."""

import os
import sys
import threading
import queue
import time
import warnings
from typing import Optional

from pastemd.utils.system_detect import is_windows, is_macos

from ...core.constants import NOTIFICATION_TIMEOUT
from ...config.paths import get_app_icon_path
from ...utils.logging import log
from ...core.state import app_state

# 忽略 win10toast 的 pkg_resources 弃用告警
warnings.filterwarnings("ignore", category=UserWarning, module="win10toast")

# --- plyer 作为最终回退 ---
try:
    from plyer import notification as _plyer_notification
    _PLYER_OK = True
except Exception:
    _PLYER_OK = False

# --- Win11 优先 ---
try:
    from win11toast import toast as _win11_toast
    _WIN11_OK = is_windows()
except Exception:
    _WIN11_OK = False

# --- Win10 次选（单例） ---
_WIN10_OK = False
_win10_toaster = None
if is_windows():
    try:
        from win10toast import ToastNotifier as _ToastNotifier
        _win10_toaster = _ToastNotifier()
        _WIN10_OK = True
    except Exception:
        _win10_toaster = None
        _WIN10_OK = False

# --- mac ---
_PYNC_OK = False
_pync_notify = None
if is_macos():
    try:
        from pync import Notifier as _PyncNotifier
        _pync_notify = _PyncNotifier
        _PYNC_OK = True
    except Exception:
        _PYNC_OK = False
        _pync_notify = None



def _icon_or_none(path: Optional[str]) -> Optional[str]:
    return path if path and os.path.exists(path) else None


def _secs_to_win11_duration(secs: int | float) -> str:
    # win11toast 的 duration 只能 'short'/'long'
    try:
        return "short" if float(secs) <= 5 else "long"
    except Exception:
        return "short"


class NotificationManager:
    """通知管理器（异步队列 + 后台线程，不阻塞热键）"""

    def __init__(self, app_name: str = "PasteMD", max_queue: int = 30):
        self.app_name = app_name
        self.icon_path = get_app_icon_path()
        self._q: "queue.Queue[tuple[str,str,bool]]" = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="NotifyWorker", daemon=True)
        self._worker.start()

    # ---- 公共接口：立即返回 ----
    def notify(self, title: str, message: str, ok: bool = True, **kwargs) -> None:
        """
        发送系统通知（异步）
        """
        log(f"Notify enqueue: {title} - {message} ({'OK' if ok else 'ERR'})")

        if app_state.config.get("notify", True) is False:
            return

        # 尝试入队；队列满时丢弃最旧一条，保证系统不被通知风暴拖垮
        try:
            self._q.put((title, message, ok), block=False)
        except queue.Full:
            try:
                _ = self._q.get_nowait()  # 丢弃最旧
            except Exception:
                pass
            try:
                self._q.put_nowait((title, message, ok))
            except Exception:
                pass  # 还是塞不进去就算了

    def is_available(self) -> bool:
        if sys.platform == "win32" and (_WIN11_OK or _WIN10_OK):
            return True
        return _PLYER_OK

    # ---- 优雅关闭（可选，应用退出时调用）----
    def shutdown(self, drain_timeout: float = 1.0) -> None:
        """请求停止 worker；可在应用退出时调用"""
        self._stop.set()
        t0 = time.time()
        while not self._q.empty() and (time.time() - t0) < drain_timeout:
            time.sleep(0.02)

    # ---- 后台线程主体 ----
    def _worker_loop(self):
        while not self._stop.is_set():
            if app_state.config.get("notify", True) is False:
                # 清空队列
                while not self._q.empty():
                    try:
                        self._q.get_nowait()
                    except Exception:
                        pass
                    finally:
                        self._q.task_done()
                time.sleep(0.25)
                continue
            try:
                title, message, ok = self._q.get(timeout=0.25)
            except queue.Empty:
                continue

            try:
                self._send_one(title, message)
            except Exception as e:
                log(f"Notification send error: {e}")
            finally:
                # 小的间隔避免连续火力太猛
                time.sleep(0.01)
                self._q.task_done()

    # ---- 具体发送实现（Win11→Win10→plyer）----
    def _send_one(self, title: str, message: str, **kwargs) -> None:
        # 1) Win11
        if _WIN11_OK:
            try:
                # 注意：此调用会阻塞直到用户关闭或超时，但在后台线程里，主线程不受影响
                _ = _win11_toast(
                    title,
                    message,
                    app_id="RichQAQ.PasteMD",
                    icon=_icon_or_none(self.icon_path),
                    duration=_secs_to_win11_duration(NOTIFICATION_TIMEOUT),
                )
                return
            except Exception as e:
                log(f"win11toast error, fallback to win10: {e}")

        # 2) Win10
        if _WIN10_OK and _win10_toaster is not None:
            try:
                _win10_toaster.show_toast(
                    title,
                    message,
                    icon_path=_icon_or_none(self.icon_path),
                    duration=int(NOTIFICATION_TIMEOUT) if NOTIFICATION_TIMEOUT else 5,
                    threaded=True,   # 本身非阻塞
                )
                return
            except Exception as e:
                log(f"win10toast error, fallback to plyer: {e}")

        if is_macos() and _PYNC_OK and _pync_notify is not None:
            try:
                _pync_notify.notify(
                    message=message,
                    title=title,
                    group="com.richqaq.pastemd",
                    appIcon=_icon_or_none(self.icon_path),
                    timeout=NOTIFICATION_TIMEOUT,
                )
                return
            except Exception as e:
                log(f"pync notify error: {e}")

        # 3) 其它平台/全部失败：plyer（避免托盘重复，仍建议不传图标）
        if _PLYER_OK:
            try:
                _plyer_notification.notify(
                    title=title,
                    message=message,
                    timeout=NOTIFICATION_TIMEOUT,
                    app_icon=self.icon_path if os.path.exists(self.icon_path) else None,
                )
            except Exception as e:
                log(f"plyer notify error: {e}")

if __name__ == "__main__":
    # 简单测试
    nm = NotificationManager()
    nm.notify("测试通知", "这是一条测试通知内容。", ok=True)
    time.sleep(3)
    nm.notify("错误通知", "这是一条错误通知内容。", ok=False)
    time.sleep(5)
