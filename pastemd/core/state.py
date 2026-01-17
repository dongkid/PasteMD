"""Global runtime state management."""

import copy
from queue import Queue
from typing import Dict, Any, Optional, Callable
import threading


class AppState:
    """
    全局应用状态（线程安全版本）

    关键属性通过 property 包装，使用 RLock 保护并发访问。
    - enabled, hotkey_str: 简单类型，通过 property 保护
    - config: 字典类型，提供安全的访问方法
    """

    def __init__(self):
        # 线程锁（使用 RLock 支持同线程重入）
        self._lock = threading.RLock()

        # 核心状态（受保护）
        self._enabled: bool = True
        self._running: bool = False
        self._hotkey_str: str = "<ctrl>+<shift>+b"
        self._config: Dict[str, Any] = {}

        # 辅助状态（不太需要严格保护）
        self.ui_block_hotkeys: bool = False
        self.last_fire: float = 0.0
        self.last_ok: bool = True

        # UI 组件引用
        self.root: Optional[Any] = None      # tkinter.Tk - 保留用于兼容
        self.listener: Optional[Any] = None  # pynput.keyboard.GlobalHotKeys
        self.icon: Optional[Any] = None      # pystray.Icon

        # WebView 组件引用
        self.webview_window: Optional[Any] = None   # webview.Window
        self.webview_manager: Optional[Any] = None  # WebViewManager

        # 单实例检查器
        self.instance_checker: Optional[Any] = None  # SingleInstanceChecker

        # UI 任务队列（Queue 本身线程安全）
        self.ui_queue: Queue = Queue()

        # 退出事件
        self.quit_event: Optional[Any] = None

    # ==================== enabled 属性（线程安全）====================

    @property
    def enabled(self) -> bool:
        """获取热键启用状态"""
        with self._lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """设置热键启用状态"""
        with self._lock:
            self._enabled = value

    # ==================== running 属性（线程安全）====================

    @property
    def running(self) -> bool:
        """获取应用运行状态"""
        with self._lock:
            return self._running

    @running.setter
    def running(self, value: bool) -> None:
        """设置应用运行状态"""
        with self._lock:
            self._running = value

    def set_running(self, running: bool) -> None:
        """线程安全设置运行状态（保持向后兼容）"""
        self.running = running

    def is_running(self) -> bool:
        """线程安全检查运行状态（保持向后兼容）"""
        return self.running

    # ==================== hotkey_str 属性（线程安全）====================

    @property
    def hotkey_str(self) -> str:
        """获取当前热键字符串"""
        with self._lock:
            return self._hotkey_str

    @hotkey_str.setter
    def hotkey_str(self, value: str) -> None:
        """设置当前热键字符串"""
        with self._lock:
            self._hotkey_str = value

    # ==================== config 属性（线程安全）====================

    @property
    def config(self) -> Dict[str, Any]:
        """
        获取配置字典

        注意：返回的是原始引用以保持向后兼容。
        对于线程安全的访问，建议使用 get_config_value() 和 update_config()。
        """
        return self._config

    @config.setter
    def config(self, value: Dict[str, Any]) -> None:
        """设置整个配置字典"""
        with self._lock:
            self._config = value

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        线程安全地获取配置值

        Args:
            key: 配置键名
            default: 默认值

        Returns:
            配置值或默认值
        """
        with self._lock:
            return self._config.get(key, default)

    def update_config(self, key: str, value: Any) -> None:
        """
        线程安全地更新单个配置项

        Args:
            key: 配置键名
            value: 配置值
        """
        with self._lock:
            self._config[key] = value

    def update_config_batch(self, updates: Dict[str, Any]) -> None:
        """
        线程安全地批量更新配置

        Args:
            updates: 要更新的键值对字典
        """
        with self._lock:
            self._config.update(updates)

    def get_config_copy(self) -> Dict[str, Any]:
        """
        获取配置的深拷贝（完全线程安全）

        Returns:
            配置字典的深拷贝
        """
        with self._lock:
            return copy.deepcopy(self._config)

    # ==================== 通用锁操作 ====================

    def with_lock(self, func: Callable[[], Any]) -> Any:
        """线程安全执行函数"""
        with self._lock:
            return func()

    # ==================== UI 队列操作 ====================

    def queue_ui_task(self, task: Callable[[], Any]) -> None:
        """
        将 UI 任务放入队列，确保在 GUI 线程执行

        用于跨线程安全调用 WebView 的 evaluate_js() 等方法。
        任务会在前端 JS 轮询时被执行。

        Args:
            task: 无参数的回调函数
        """
        self.ui_queue.put(task)

    def process_ui_queue(self) -> int:
        """
        处理 UI 任务队列中的所有待执行任务

        Returns:
            处理的任务数量
        """
        count = 0
        while not self.ui_queue.empty():
            try:
                task = self.ui_queue.get_nowait()
                task()
                count += 1
            except Exception:
                pass
        return count


# 全局状态实例
app_state = AppState()
