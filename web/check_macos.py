#!/usr/bin/env python3
"""
macOS 环境检测脚本
检查 pywebview 在 macOS 上运行所需的环境
"""

import sys
import subprocess


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    print(f"✓ Python 版本: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("  ⚠️ 建议使用 Python 3.8+")
        return False
    return True


def check_platform():
    """检查平台"""
    platform = sys.platform
    print(f"✓ 平台: {platform}")
    if platform != "darwin":
        print("  ⚠️ 当前不是 macOS 系统")
        return False
    return True


def check_pywebview():
    """检查 pywebview 安装"""
    try:
        import webview
        print(f"✓ pywebview 版本: {webview.__version__ if hasattr(webview, '__version__') else '已安装'}")
        return True
    except ImportError:
        print("✗ pywebview 未安装")
        print("  运行: pip install pywebview")
        return False


def check_pyobjc():
    """检查 PyObjC (macOS 必需)"""
    try:
        import objc
        print("✓ PyObjC: 已安装")
        return True
    except ImportError:
        print("✗ PyObjC 未安装")
        print("  运行: pip install pyobjc pyobjc-framework-Cocoa pyobjc-framework-WebKit")
        return False


def check_webkit():
    """检查 WebKit 框架"""
    try:
        from WebKit import WKWebView
        print("✓ WebKit 框架: 可用")
        return True
    except ImportError:
        print("⚠️ WebKit 框架导入失败，但通常 macOS 自带")
        return True  # macOS 通常自带 WebKit


def check_permissions():
    """检查必要权限提示"""
    print("\n📋 macOS 权限说明:")
    print("  - pywebview 使用 Cocoa + WebKit，无需额外权限")
    print("  - 如果打包为 .app，可能需要配置 Info.plist")
    print("  - 与 pystray 托盘集成时，需要注意主线程问题")
    return True


def run_webview_test():
    """尝试运行简单的 webview 测试"""
    print("\n🧪 尝试创建 webview 窗口...")
    try:
        import webview

        def on_loaded():
            print("✓ WebView 窗口加载成功!")
            # 2秒后自动关闭
            import threading
            def close():
                import time
                time.sleep(2)
                for window in webview.windows:
                    window.destroy()
            threading.Thread(target=close, daemon=True).start()

        window = webview.create_window(
            "pywebview macOS 测试",
            html="<h1 style='text-align:center;margin-top:50px;font-family:system-ui;'>✅ pywebview 在 macOS 上工作正常!</h1>",
            width=400,
            height=200
        )
        window.events.loaded += on_loaded
        webview.start()
        return True
    except Exception as e:
        print(f"✗ WebView 测试失败: {e}")
        return False


def main():
    print("=" * 50)
    print("macOS pywebview 环境检测")
    print("=" * 50)
    print()

    checks = [
        ("Python 版本", check_python_version),
        ("平台检测", check_platform),
        ("pywebview", check_pywebview),
    ]

    # 只在 macOS 上检查这些
    if sys.platform == "darwin":
        checks.extend([
            ("PyObjC", check_pyobjc),
            ("WebKit", check_webkit),
        ])

    all_passed = True
    for name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"✗ {name} 检测出错: {e}")
            all_passed = False
        print()

    check_permissions()

    print()
    print("=" * 50)
    if all_passed:
        print("✅ 环境检测通过!")
        if sys.platform == "darwin":
            response = input("\n是否运行 webview 测试? (y/n): ")
            if response.lower() == 'y':
                run_webview_test()
    else:
        print("⚠️ 部分检测未通过，请查看上方详情")
    print("=" * 50)


if __name__ == "__main__":
    main()
