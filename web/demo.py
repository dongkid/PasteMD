"""
WebView 界面验证示例
验证 pywebview 在 PasteMD 项目中的可行性

跨平台支持:
- Windows: EdgeChromium (推荐) / MSHTML / CEF
- macOS: WebKit (Cocoa) - 需要在主线程运行
- Linux: WebKitGTK / CEF
"""

import webview
import json
import sys
from pathlib import Path


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return sys.platform == "win32"


class Api:
    """Python 与 JavaScript 通信的 API 类"""

    def __init__(self):
        self.settings = {
            "hotkey": "<ctrl>+<shift>+b",
            "language": "zh-CN",
            "no_app_action": "notify"
        }

    def get_settings(self) -> str:
        """获取设置 (JS 调用)"""
        return json.dumps(self.settings)

    def save_settings(self, settings_json: str) -> str:
        """保存设置 (JS 调用)"""
        try:
            self.settings = json.loads(settings_json)
            print(f"[Python] 设置已保存: {self.settings}")
            return json.dumps({"success": True, "message": "设置已保存"})
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)})

    def get_version(self) -> str:
        """获取版本信息"""
        return "PasteMD WebView Demo v0.1"

    def close_window(self):
        """关闭窗口"""
        webview.windows[0].destroy()


def get_platform_info() -> dict:
    """获取平台信息"""
    info = {
        "platform": sys.platform,
        "python_version": sys.version,
    }

    if is_macos():
        info["gui_backend"] = "cocoa"
        info["notes"] = "使用 WebKit 渲染引擎"
    elif is_windows():
        info["gui_backend"] = "edgechromium"
        info["notes"] = "使用 EdgeChromium 渲染引擎"
    else:
        info["gui_backend"] = "gtk"
        info["notes"] = "使用 WebKitGTK 渲染引擎"

    return info


def main():
    # 打印平台信息
    platform_info = get_platform_info()
    print(f"[WebView] 平台: {platform_info['platform']}")
    print(f"[WebView] GUI 后端: {platform_info['gui_backend']}")
    print(f"[WebView] 说明: {platform_info['notes']}")

    # 获取 HTML 文件路径
    html_path = Path(__file__).parent / "index.html"

    # 创建 API 实例
    api = Api()

    # macOS 特定配置
    window_config = {
        "title": "PasteMD 设置",
        "url": str(html_path),
        "width": 600,
        "height": 500,
        "resizable": True,
        "min_size": (400, 300),
        "js_api": api,
        "background_color": "#1e1e1e",
    }

    # macOS 下可以添加额外配置
    if is_macos():
        window_config["text_select"] = True  # 允许文本选择

    # 创建窗口
    window = webview.create_window(**window_config)

    # 启动 webview
    # macOS 需要特别注意: webview 必须在主线程启动
    # 如果与其他 GUI 库 (如 pystray) 集成，需要特殊处理
    start_config = {
        "debug": True,
    }

    # macOS 使用 cocoa 后端
    if is_macos():
        # cocoa 是 macOS 的原生后端，无需额外安装
        pass
    elif is_windows():
        # Windows 优先使用 EdgeChromium
        # 如果没有 Edge，会回退到 MSHTML 或需要安装 CEF
        pass

    webview.start(**start_config)


if __name__ == "__main__":
    main()
