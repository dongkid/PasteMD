#!/usr/bin/env python3
"""
PasteMD Frontend Development Server

用于实时调试前端 CSS/JS，无需重启应用。

使用方法:
    python dev_server.py

然后在浏览器中打开 http://localhost:8086
修改 CSS/JS 后刷新浏览器即可看到效果。

特性:
- 完整模拟 pywebview API (返回正确格式的 mock 数据)
- 支持热重载 (需要手动刷新浏览器)
- 自动注入 mock API 脚本
- 侧边栏、主题切换、设置修改都能正常工作
"""

import http.server
import json
import os
import socketserver
from urllib.parse import urlparse

PORT = 8086
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "pastemd", "presentation", "webview", "assets")

# Mock 配置数据
MOCK_SETTINGS = {
    "hotkey": "<ctrl>+<shift>+b",
    "theme": "dark",
    "language": "zh-CN",
    "notification_enabled": True,
    "autostart": False,
    "no_app_action": "notify",
    "enable_excel": True,
    "excel_keep_format": False,
    "move_cursor_to_end": True,
    "debug_mode": True,
    "reference_docx": "",
    "Keep_original_formula": False,
    "save_dir": "~/Documents/PasteMD",
    "keep_file": False,
    "notify": True,
    "startup_notify": True,
    "pandoc_path": "pandoc",
    "html_formatting": {"strikethrough_to_del": True},
    "md_disable_first_para_indent": False,
    "html_disable_first_para_indent": False,
    "enable_latex_replacements": False,
    "fix_single_dollar_block": False,
    "pandoc_filters": [],
    "pandoc_request_headers": [],
    "extensions": {},
}

MOCK_LANGUAGES = [
    {"code": "zh-CN", "label": "简体中文"},
    {"code": "en-US", "label": "English"},
    {"code": "ja-JP", "label": "日本語"},
]

MOCK_THEME_OPTIONS = [
    {"value": "auto", "label": "跟随系统"},
    {"value": "light", "label": "浅色"},
    {"value": "dark", "label": "深色"},
]

MOCK_NO_APP_ACTIONS = [
    {"value": "notify", "label": "显示通知"},
    {"value": "open", "label": "打开设置"},
    {"value": "ignore", "label": "忽略"},
]

MOCK_PLATFORM = {
    "is_windows": True,
    "is_macos": False,
}

# 读取翻译文件
def load_translations():
    """加载中文翻译文件"""
    locale_path = os.path.join(
        os.path.dirname(__file__),
        "pastemd", "i18n", "locales", "zh-CN.json"
    )
    try:
        with open(locale_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] Failed to load translations: {e}")
        return {}


# Mock pywebview API 的 JavaScript 代码
def get_mock_api_script():
    """生成 Mock API 脚本"""
    translations = load_translations()

    return """
<script>
// ============================================================
// Mock pywebview API for Development
// ============================================================

// 内存中的设置状态 (可修改)
const mockState = {
    settings: %s,
    translations: %s,
};

// API 响应包装器
function success(data) {
    return { success: true, data: data };
}

function error(message) {
    return { success: false, error: { message: message } };
}

// Mock pywebview.api
window.pywebview = {
    api: {
        // ==================== Settings API ====================
        get_settings: () => {
            console.log('[Mock API] get_settings');
            return Promise.resolve(success(mockState.settings));
        },

        save_settings: (settingsJson) => {
            const settings = JSON.parse(settingsJson);
            console.log('[Mock API] save_settings:', settings);
            // 更新内存中的设置
            Object.assign(mockState.settings, settings);
            return Promise.resolve(success(true));
        },

        get_languages: () => {
            console.log('[Mock API] get_languages');
            return Promise.resolve(success(%s));
        },

        get_theme_options: () => {
            console.log('[Mock API] get_theme_options');
            return Promise.resolve(success(%s));
        },

        get_no_app_actions: () => {
            console.log('[Mock API] get_no_app_actions');
            return Promise.resolve(success(%s));
        },

        get_platform: () => {
            console.log('[Mock API] get_platform');
            return Promise.resolve(success(%s));
        },

        get_translations: () => {
            console.log('[Mock API] get_translations');
            return Promise.resolve(success(mockState.translations));
        },

        get_default_config: () => {
            console.log('[Mock API] get_default_config');
            return Promise.resolve(success({
                save_dir: "~/Documents/PasteMD",
                pandoc_path: "pandoc"
            }));
        },

        expand_path: (path) => {
            console.log('[Mock API] expand_path:', path);
            return Promise.resolve(success(path.replace("~", "C:/Users/Dev")));
        },

        browse_directory: (initialDir) => {
            console.log('[Mock API] browse_directory:', initialDir);
            return Promise.resolve(success("C:/Users/Dev/Documents/PasteMD"));
        },

        browse_file: (fileTypes, initialDir) => {
            console.log('[Mock API] browse_file:', fileTypes, initialDir);
            return Promise.resolve(success("C:/Users/Dev/Documents/example.docx"));
        },

        close_window: () => {
            console.log('[Mock API] close_window (ignored in dev mode)');
            return Promise.resolve(success(true));
        },

        minimize_window: () => {
            console.log('[Mock API] minimize_window (ignored in dev mode)');
            return Promise.resolve(success(true));
        },

        // ==================== Platform Effects API ====================
        update_mica_theme: (theme) => {
            console.log('[Mock API] update_mica_theme:', theme);
            return Promise.resolve(success(true));
        },

        get_platform_capabilities: () => {
            console.log('[Mock API] get_platform_capabilities');
            return Promise.resolve(success({
                mica_supported: false,  // 浏览器中无 Mica
                vibrancy_supported: false,
                transparent_supported: false
            }));
        },

        // ==================== UI Queue (no-op) ====================
        process_ui_queue: () => {
            return Promise.resolve(success(null));
        },

        // ==================== Hotkey API ====================
        hotkey: {
            get_current_hotkey: () => {
                console.log('[Mock API] hotkey.get_current_hotkey');
                return Promise.resolve(success({
                    raw: mockState.settings.hotkey,
                    formatted: mockState.settings.hotkey
                        .replace(/</g, '').replace(/>/g, '')
                        .replace(/\\+/g, ' + ')
                        .split(' + ')
                        .map(k => k.charAt(0).toUpperCase() + k.slice(1))
                        .join(' + ')
                }));
            },

            start_recording_windows: () => {
                console.log('[Mock API] hotkey.start_recording_windows');
                return Promise.resolve(success(true));
            },

            stop_recording_windows: () => {
                console.log('[Mock API] hotkey.stop_recording_windows');
                return Promise.resolve(success("<ctrl>+<shift>+b"));
            },

            validate_hotkey: (keysJson) => {
                console.log('[Mock API] hotkey.validate_hotkey:', keysJson);
                return Promise.resolve(success({ valid: true }));
            },

            check_hotkey_conflict: (hotkeyStr) => {
                console.log('[Mock API] hotkey.check_hotkey_conflict:', hotkeyStr);
                return Promise.resolve(success({ is_available: true }));
            },

            save_hotkey: (hotkeyStr) => {
                console.log('[Mock API] hotkey.save_hotkey:', hotkeyStr);
                mockState.settings.hotkey = hotkeyStr;
                return Promise.resolve(success(true));
            },

            get_platform: () => {
                console.log('[Mock API] hotkey.get_platform');
                return Promise.resolve(success("windows"));
            }
        },

        // ==================== Permissions API ====================
        permissions: {
            is_macos: () => {
                return Promise.resolve(success(false));
            },

            get_all_permissions: () => {
                console.log('[Mock API] permissions.get_all_permissions');
                return Promise.resolve(success({
                    accessibility: { status: "granted" },
                    automation: { status: "granted" }
                }));
            },

            check_permission: (type) => {
                console.log('[Mock API] permissions.check_permission:', type);
                return Promise.resolve(success({ status: "granted" }));
            },

            request_permission: (type) => {
                console.log('[Mock API] permissions.request_permission:', type);
                return Promise.resolve(success(true));
            },

            open_system_settings: (type) => {
                console.log('[Mock API] permissions.open_system_settings:', type);
                return Promise.resolve(success(true));
            },

            get_permission_info: () => {
                return Promise.resolve(success({}));
            }
        },

        // ==================== Extensions API ====================
        extensions: {
            get_available_apps: () => {
                console.log('[Mock API] extensions.get_available_apps');
                return Promise.resolve(success([
                    { name: "Microsoft Word", id: "WINWORD.EXE" },
                    { name: "WPS Writer", id: "wps.exe" },
                    { name: "Visual Studio Code", id: "Code.exe" },
                ]));
            },

            get_extensions: () => {
                console.log('[Mock API] extensions.get_extensions');
                return Promise.resolve(success(mockState.settings.extensions || {}));
            },

            save_extension: (appId, extJson) => {
                console.log('[Mock API] extensions.save_extension:', appId, extJson);
                if (!mockState.settings.extensions) {
                    mockState.settings.extensions = {};
                }
                mockState.settings.extensions[appId] = JSON.parse(extJson);
                return Promise.resolve(success(true));
            },

            delete_extension: (appId) => {
                console.log('[Mock API] extensions.delete_extension:', appId);
                if (mockState.settings.extensions) {
                    delete mockState.settings.extensions[appId];
                }
                return Promise.resolve(success(true));
            }
        }
    }
};

// 立即触发 pywebviewready 事件
console.log('[Dev Server] Mock pywebview API injected');
console.log('[Dev Server] 修改 CSS/JS 后刷新浏览器即可生效');
console.log('[Dev Server] 设置修改会保存在内存中，刷新后重置');

// 延迟触发 pywebviewready 事件，确保其他脚本已加载
setTimeout(() => {
    window.dispatchEvent(new Event('pywebviewready'));
    console.log('[Dev Server] pywebviewready event dispatched');
}, 100);
</script>
""" % (
        json.dumps(MOCK_SETTINGS),
        json.dumps(translations),
        json.dumps(MOCK_LANGUAGES),
        json.dumps(MOCK_THEME_OPTIONS),
        json.dumps(MOCK_NO_APP_ACTIONS),
        json.dumps(MOCK_PLATFORM),
    )


class DevServerHandler(http.server.SimpleHTTPRequestHandler):
    """开发服务器 Handler，支持 Mock API 注入"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ASSETS_DIR, **kwargs)

    def do_GET(self):
        """处理 GET 请求，为 HTML 文件注入 Mock API"""
        parsed = urlparse(self.path)
        path = parsed.path

        # 根路径重定向到 index.html
        if path == "/" or path == "":
            path = "/index.html"

        # 如果是 HTML 文件，注入 Mock API
        if path.endswith(".html"):
            file_path = os.path.join(ASSETS_DIR, path.lstrip("/"))
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 在 </head> 前注入 Mock API 脚本
                    mock_script = get_mock_api_script()
                    content = content.replace("</head>", mock_script + "</head>")

                    # 发送响应
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", len(content.encode("utf-8")))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.end_headers()
                    self.wfile.write(content.encode("utf-8"))
                    return
                except Exception as e:
                    self.send_error(500, str(e))
                    return

        # 其他文件正常处理，但禁用缓存
        super().do_GET()

    def end_headers(self):
        """添加禁用缓存的响应头"""
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main():
    """启动开发服务器"""
    print("=" * 60)
    print("  PasteMD Frontend Development Server")
    print("=" * 60)
    print()
    print(f"  Assets directory: {ASSETS_DIR}")
    print(f"  Server URL: http://localhost:{PORT}")
    print()
    print("  Features:")
    print("    ✓ Mock pywebview API (完整模拟)")
    print("    ✓ 禁用缓存 (修改后刷新即生效)")
    print("    ✓ 浏览器 DevTools 完整支持")
    print("    ✓ 侧边栏导航正常工作")
    print("    ✓ 主题切换正常工作")
    print("    ✓ 设置修改保存在内存中")
    print()
    print("  Usage:")
    print("    1. 在浏览器中打开 http://localhost:8086")
    print("    2. 修改 CSS/JS 文件")
    print("    3. 刷新浏览器查看效果")
    print("    4. Ctrl+C 停止服务器")
    print()
    print("=" * 60)
    print()

    with socketserver.TCPServer(("", PORT), DevServerHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Dev Server] Shutting down...")


if __name__ == "__main__":
    main()
