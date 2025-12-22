"""Hotkey binding manager."""

from typing import Optional, Callable
import threading
from pynput import keyboard

from ...utils.logging import log
from ...utils.system_detect import is_macos


class HotkeyManager:
    """热键管理器 - 负责全局热键监听和触发"""
    
    def __init__(self):
        self.global_listener: Optional[keyboard.GlobalHotKeys] = None  # 全局热键监听器
        self.current_hotkey: Optional[str] = None
        self._mac_listener: Optional[keyboard.Listener] = None
        self._mac_hotkey: Optional[keyboard.HotKey] = None
        self._mac_lock = threading.Lock()

    def _mac_ensure_listener(self) -> None:
        if self._mac_listener:
            return

        def on_press(key):
            with self._mac_lock:
                hotkey_obj = self._mac_hotkey
            if not hotkey_obj:
                return
            try:
                hotkey_obj.press(key)
            except Exception:
                pass

        def on_release(key):
            with self._mac_lock:
                hotkey_obj = self._mac_hotkey
            if not hotkey_obj:
                return
            try:
                hotkey_obj.release(key)
            except Exception:
                pass

        self._mac_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._mac_listener.daemon = True
        self._mac_listener.start()

    def _mac_set_hotkey(self, hotkey: Optional[str], callback: Optional[Callable[[], None]]) -> None:
        with self._mac_lock:
            if not hotkey or not callback:
                self._mac_hotkey = None
                return

            def on_activate():
                try:
                    callback()
                except Exception as e:
                    log(f"Hotkey callback error: {e}")

            keys = keyboard.HotKey.parse(hotkey)
            self._mac_hotkey = keyboard.HotKey(keys, on_activate)

    def _stop_listener(self, *, keep_hotkey: bool) -> None:
        listener = self.global_listener
        if not listener:
            return

        try:
            listener.stop()
            log(f"Hotkey listener stopped: {self.current_hotkey}")
        except Exception as e:
            log(f"Error stopping hotkey listener: {e}")
        finally:
            # Ensure the listener thread is actually torn down before restarting.
            try:
                if hasattr(listener, "join"):
                    listener.join(timeout=1.0)
                    if getattr(listener, "is_alive", lambda: False)():
                        log("Hotkey listener thread is still alive after stop()")
            except Exception as e:
                log(f"Error joining hotkey listener thread: {e}")

            self.global_listener = None
            if not keep_hotkey:
                self.current_hotkey = None
    
    def bind(self, hotkey: str, callback: Callable[[], None]) -> None:
        """
        绑定全局热键
        
        Args:
            hotkey: 热键字符串 (例如: "<ctrl>+<shift>+b")
            callback: 热键触发时的回调函数
        """
        if is_macos():
            self._mac_ensure_listener()
            self._mac_set_hotkey(hotkey, callback)
            self.current_hotkey = hotkey
            log(f"Hotkey bound: {hotkey}")
            return

        # 停止现有监听器
        self.unbind()
        
        try:
            mapping = {hotkey: callback}
            self.global_listener = keyboard.GlobalHotKeys(mapping)
            self.global_listener.daemon = True
            self.global_listener.start()
            self.current_hotkey = hotkey
            log(f"Hotkey bound: {hotkey}")
            
        except Exception as e:
            log(f"Failed to bind hotkey {hotkey}: {e}")
            raise
    
    def unbind(self) -> None:
        """解绑当前热键"""
        if is_macos():
            previous_hotkey = self.current_hotkey
            self._mac_set_hotkey(None, None)
            self.current_hotkey = None
            log(f"Hotkey unbound: {previous_hotkey}")
            return

        if not self.global_listener:
            return

        previous_hotkey = self.current_hotkey
        self._stop_listener(keep_hotkey=False)
        log(f"Hotkey unbound: {previous_hotkey}")
    
    def restart(self, hotkey: str, callback: Callable[[], None]) -> None:
        """重启热键绑定"""
        self.unbind()
        self.bind(hotkey, callback)
    
    def is_bound(self) -> bool:
        """检查是否有热键绑定"""
        if is_macos():
            with self._mac_lock:
                return self._mac_hotkey is not None and self.current_hotkey is not None
        return self.global_listener is not None and self.current_hotkey is not None
    
    def pause(self) -> None:
        """暂停热键监听（用于录制时避免触发）"""
        if is_macos():
            if not self.current_hotkey:
                return
            self._mac_set_hotkey(None, None)
            log(f"Hotkey paused: {self.current_hotkey}")
            return

        if not self.global_listener:
            return

        self._stop_listener(keep_hotkey=True)
        log(f"Hotkey paused: {self.current_hotkey}")
    
    def resume(self, callback: Callable[[], None]) -> None:
        """恢复热键监听"""
        if is_macos():
            if not self.current_hotkey:
                return
            with self._mac_lock:
                if self._mac_hotkey is not None:
                    return
            self._mac_ensure_listener()
            self._mac_set_hotkey(self.current_hotkey, callback)
            log(f"Hotkey resumed: {self.current_hotkey}")
            return

        if not self.current_hotkey:
            return
        if self.global_listener:
            return

        try:
            mapping = {self.current_hotkey: callback}
            self.global_listener = keyboard.GlobalHotKeys(mapping)
            self.global_listener.daemon = True
            self.global_listener.start()
            log(f"Hotkey resumed: {self.current_hotkey}")
        except Exception as e:
            log(f"Error resuming hotkey listener: {e}")
