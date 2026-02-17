# PasteMD Linux 支持可行性研究报告

> 生成日期: 2026-02-10
> 研究人员: PasteMD Architecture Team

---

## 摘要

本文档研究 PasteMD 项目添加 Linux 系统支持的可能性，重点关注 WPS Office Linux 版本的集成方案。

**核心发现**: 通过 `pywpsrpc` 库，WPS Linux 版本具备较完整的 RPC API，可覆盖核心文档/表格插入场景，能力接近 Windows COM 集成（仍需实机回归验证）。

---

## 目录

1. [项目概述](#1-项目概述)
2. [现有架构分析](#2-现有架构分析)
3. [Linux 平台支持现状](#3-linux-平台支持现状)
4. [WPS Linux 集成方案](#4-wps-linux-集成方案)
5. [Linux 托盘图标方案](#5-linux-托盘图标方案)
6. [技术实现路线图](#6-技术实现路线图)
7. [风险与挑战](#7-风险与挑战)
8. [总结与建议](#8-总结与建议)
9. [附录](#9-附录)

---

## 1. 项目概述

### 1.1 PasteMD 简介

PasteMD 是一个跨平台剪贴板内容转换工具，主要功能包括：

- **格式转换**: HTML ↔ Markdown ↔ LaTeX ↔ DOCX ↔ RTF
- **富文本粘贴**: 直接粘贴到 Word、WPS、Excel 等办公软件
- **全局热键**: Ctrl+Shift+B 触发粘贴
- **多平台支持**: Windows + macOS

### 1.2 技术栈

| 组件 | 技术选择 |
|------|----------|
| GUI 框架 | pystray + Tkinter |
| 热键监听 | pynput |
| 文档转换 | Pandoc |
| Windows 集成 | win32com |
| macOS 集成 | AppleScript + PyObjC |

### 1.3 版本信息

- **Python 版本**: 3.12+
- **当前状态**: Windows + macOS 稳定版
- **Linux 支持**: 规划中

---

## 2. 现有架构分析

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PasteMD 架构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                      应用层 (app/)                            │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │
│   │  │  app.py  │ │ wiring.py│ │ workflows│ │  tray/   │       │   │
│   │  │ 入口点   │ │ DI 容器   │ │ 工作流   │ │ 托盘菜单 │       │   │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                      核心层 (core/)                          │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │
│   │  │ state.py │ │constants │ │ types.py │ │ errors.py│       │   │
│   │  │ 全局状态  │ │  常量    │ │  类型    │ │  错误    │       │   │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                      服务层 (service/)                        │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │
│   │  │ hotkey/  │ │notification│ │document/│ │spreadsheet│       │   │
│   │  │ 热键服务 │ │  通知    │ │ 文档处理 │ │  表格    │       │   │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                      工具层 (utils/)                        │   │
│   │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │   │
│   │  │ win32/   │ │ macos/   │ │ clipboard│ │ detector │       │   │
│   │  │ Windows  │ │  macOS   │ │ 剪贴板   │ │ 应用检测 │       │   │
│   │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 工作流路由器

```mermaid
graph TD
    A[热键触发] --> B[detect_active_app]
    B --> C{检测结果}
    
    C -->|word| D[WordWorkflow]
    C -->|wps| E[WPSWorkflow]
    C -->|excel| F[ExcelWorkflow]
    C -->|wps_excel| G[WPSExcelWorkflow]
    C -->|onenote| H[OneNoteWorkflow]
    C -->|powerpoint| I[PowerPointWorkflow]
    C -->|""| J[FallbackWorkflow]
    
    D --> K[插入 DOCX]
    E --> K
    F --> L[插入 Excel]
    G --> L
    J --> M[剪贴板粘贴]
```

### 2.3 文档处理流水线

```
剪贴板内容
    │
    ├─ HTML ─→ HTML 预处理器 ─→ Pandoc HTML→DOCX ─→ DOCX Placer
    │
    ├─ Markdown ─→ Markdown 预处理器 ─→ Pandoc MD→DOCX ─→ DOCX Placer
    │
    └─ Excel 数据 ─→ Excel 处理器 ─→ 表格 Placer
```

---

## 3. Linux 平台支持现状

### 3.1 当前实现

当前 `clipboard.py` 中的 Linux 后备方案：

```python
# pastemd/utils/clipboard.py

else:
    # 其他平台的后备实现（仅支持基本文本功能）
    import pyperclip

    def get_clipboard_text() -> str:
        """获取剪贴板文本内容"""
        try:
            text = pyperclip.paste()
            if text is None:
                return ""
            return text
        except Exception as e:
            raise ClipboardError(f"Failed to read clipboard: {e}")

    def is_clipboard_html() -> bool:
        """检查剪切板内容是否为 HTML 富文本"""
        return False  # 不支持
```

### 3.2 功能缺失矩阵

| 功能模块 | Windows | macOS | Linux |
|---------|---------|-------|-------|
| **剪贴板文本** | ✅ | ✅ | ✅ pyperclip |
| **剪贴板 HTML** | ✅ CF_HTML | ✅ NSPasteboard | ❌ 不支持 |
| **富文本粘贴** | ✅ COM | ✅ AppleScript | ❌ 不支持 |
| **Word 集成** | ✅ COM | ✅ AppleScript | ❌ 不支持 |
| **WPS 集成** | ✅ COM | ❌ 不支持 | ❌ 未实现 |
| **Excel 集成** | ✅ COM | ✅ AppleScript | ❌ 未实现 |
| **热键监听** | ✅ pynput | ✅ pynput | ✅ pynput |
| **系统通知** | ✅ Win11/10 | ✅ Native | ⚠️ plyer 回退 |
| **托盘图标** | ✅ pystray | ✅ pystray | ✅ pystray |

### 3.3 现有 Linux 相关代码

```python
# pastemd/utils/system_detect.py

def is_linux() -> bool:
    return get_os_name() == "linux"
```

当前仅用于条件检查，无实际 Linux 实现。

---

## 4. WPS Linux 集成方案

### 4.1 关键发现：pywpsrpc

经过研究，发现 WPS Office Linux 提供官方 RPC API，通过 `pywpsrpc` 库可以完全控制 WPS。

#### 4.1.1 pywpsrpc 概述

| 属性 | 值 |
|------|-----|
| **项目地址** | https://github.com/timxx/pywpsrpc |
| **PyPI 包名** | pywpsrpc |
| **Stars** | 283 |
| **Forks** | 52 |
| **许可证** | MIT |
| **Python 版本** | 3.6+ |

#### 4.1.2 系统要求

- WPS Office Linux 11.1.0.9080+
- Qt5 运行时库
- 桌面环境（X11 或 Wayland）

#### 4.1.3 安装方式

```bash
# 从 PyPI 安装（推荐）
pip install pywpsrpc

# 从源码安装
git clone https://github.com/timxx/pywpsrpc.git
cd pywpsrpc
sip-build
pip install dist/pywpsrpc-*.whl
```

### 4.2 WPS Linux RPC API 详解

#### 4.2.1 可用模块

| 模块 | 用途 | 对应 WPS 应用 |
|------|------|---------------|
| `rpcwpsapi` | WPS 文字 API | wps |
| `rpcetapi` | WPS 表格 API | et |
| `rpcwppapi` | WPS 演示 API | wpp |
| `common` | 公共接口 | - |

#### 4.2.2 快速上手示例

```python
from pywpsrpc.rpcwpsapi import createWpsRpcInstance, wpsapi
from pywpsrpc import RpcIter

# 创建 RPC 实例
hr, rpc = createWpsRpcInstance()
assert hr == 0, "创建 RPC 实例失败"

# 获取 WPS 应用
hr, app = rpc.getWpsApplication()
assert hr == 0, "获取 WPS 应用失败"

# 创建新文档
hr, doc = app.Documents.Add()

# 插入文本
selection = app.Selection
selection.InsertAfter("Hello, WPS on Linux!")

# 设置格式
selection.Font.Bold = True
selection.Font.Size = 16

# 保存文档
doc.SaveAs2("/tmp/test.docx")

# 退出
app.Quit(wpsapi.wdDoNotSaveChanges)
```

#### 4.2.3 文档格式转换示例

```python
from pywpsrpc.rpcwpsapi import createWpsRpcInstance, wpsapi
from pywpsrpc.common import S_OK

formats = {
    "doc": wpsapi.wdFormatDocument,
    "docx": wpsapi.wdFormatXMLDocument,
    "rtf": wpsapi.wdFormatRTF,
    "html": wpsapi.wdFormatHTML,
    "pdf": wpsapi.wdFormatPDF,
}

def convert_to(docx_path, output_format):
    hr, rpc = createWpsRpcInstance()
    hr, app = rpc.getWpsApplication()
    
    # 打开文档
    hr, doc = app.Documents.Open(docx_path)
    
    # 保存为其他格式
    output_path = docx_path.replace(".docx", f".{output_format}")
    doc.SaveAs2(output_path, FileFormat=formats[output_format])
    
    # 关闭文档
    doc.Close(wpsapi.wdDoNotSaveChanges)
    
    app.Quit(wpsapi.wdDoNotSaveChanges)
```

### 4.3 WPS Linux 落地器设计

#### 4.3.1 文件结构

```
pastemd/service/document/linux/
├── __init__.py
├── wps.py              # WPS 落地器主类
└── wps_inserter.py     # 文档插入器
```

#### 4.3.2 WPS 落地器实现

```python
# pastemd/service/document/linux/wps.py

import os
import tempfile
from typing import Optional, Any

from pywpsrpc.rpcwpsapi import createWpsRpcInstance, wpsapi
from pywpsrpc.common import S_OK

from ....core.errors import InsertError
from ....core.types import PlacementResult
from ....utils.logging import log
from ....i18n import t


class WPSLinuxPlacer:
    """WPS Linux 内容落地器 - 基于 pywpsrpc"""
    
    def __init__(self):
        self._app: Optional[Any] = None
        self._rpc: Optional[Any] = None
    
    def connect(self) -> bool:
        """
        连接到 WPS 进程
        
        Returns:
            True 如果连接成功
        """
        hr, rpc = createWpsRpcInstance()
        if hr != S_OK:
            log(f"无法创建 WPS RPC 实例: {hex(hr)}")
            return False
        
        hr, app = rpc.getWpsApplication()
        if hr != S_OK:
            log(f"无法获取 WPS 应用: {hex(hr)}")
            return False
        
        self._rpc = rpc
        self._app = app
        log("成功连接到 WPS Linux")
        return True
    
    def place(self, docx_bytes: bytes, config: dict) -> PlacementResult:
        """
        插入 DOCX 内容
        
        Args:
            docx_bytes: DOCX 文件字节流
            config: 配置字典
            
        Returns:
            PlacementResult: 插入结果
        """
        if not self._app:
            if not self.connect():
                return PlacementResult(
                    success=False,
                    error=t("placer.linux_wps.connection_failed")
                )
        
        try:
            # 临时文件方式插入
            with tempfile.NamedTemporaryFile(
                suffix=".docx",
                delete=False
            ) as tmp:
                tmp.write(docx_bytes)
                tmp_path = tmp.name
            
            try:
                # 打开并复制内容
                hr, doc = self._app.Documents.Open(tmp_path)
                if hr != S_OK:
                    raise InsertError(f"打开文档失败: {hex(hr)}")
                
                # 全选并复制
                self._app.ActiveDocument.Content.Copy()
                
                # 关闭原文档（不保存）
                doc.Close(wpsapi.wdDoNotSaveChanges)
                
                log("DOCX 内容已复制到剪贴板")
                
                # 模拟粘贴（需要 xdotool）
                # self._simulate_paste()
                
                return PlacementResult(success=True, method="rpc_copy")
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        
        except Exception as e:
            log(f"WPS Linux 插入失败: {e}")
            return PlacementResult(
                success=False,
                method="rpc_copy",
                error=str(e)
            )
    
    def insert_text(self, text: str) -> PlacementResult:
        """
        直接插入文本
        
        Args:
            text: 要插入的文本
            
        Returns:
            PlacementResult: 插入结果
        """
        if not self._app:
            if not self.connect():
                return PlacementResult(
                    success=False,
                    error=t("placer.linux_wps.connection_failed")
                )
        
        try:
            selection = self._app.Selection
            selection.InsertAfter(text)
            return PlacementResult(success=True, method="rpc_text")
        except Exception as e:
            log(f"WPS Linux 文本插入失败: {e}")
            return PlacementResult(
                success=False,
                method="rpc_text",
                error=str(e)
            )
    
    def quit(self):
        """退出 WPS"""
        if self._app:
            try:
                self._app.Quit(wpsapi.wdDoNotSaveChanges)
                log("WPS 已退出")
            except Exception as e:
                log(f"退出 WPS 失败: {e}")
```

#### 4.3.3 WPS Excel 落地器

```python
# pastemd/service/spreadsheet/linux/wps_excel.py

from pywpsrpc.rpcetapi import createEtRpcInstance, etapi
from pywpsrpc.common import S_OK
from ....utils.logging import log

class WPSExcelLinuxPlacer:
    """WPS 表格 Linux 落地器"""
    
    def __init__(self):
        self._app = None
        self._rpc = None
    
    def connect(self) -> bool:
        hr, rpc = createEtRpcInstance()
        if hr != S_OK:
            return False
        
        hr, app = rpc.getEtApplication()
        if hr != S_OK:
            return False
        
        self._rpc = rpc
        self._app = app
        return True
    
    def paste_data(self, data: str) -> bool:
        """
        粘贴表格数据
        
        Args:
            data: CSV 或制表符分隔的数据
            
        Returns:
            True 如果粘贴成功
        """
        if not self._app:
            if not self.connect():
                return False
        
        try:
            # 获取活动工作表
            sheet = self._app.ActiveSheet
            
            # 在当前位置粘贴
            selection = self._app.Selection
            selection.Paste()
            
            return True
        except Exception as e:
            log(f"WPS Excel 粘贴失败: {e}")
            return False
```

### 4.4 Linux 应用检测

```python
# pastemd/utils/linux/detector.py

import subprocess
import re
from typing import Literal

AppType = Literal["wps", "wps_excel", ""]


def detect_active_app() -> AppType:
    """
    检测当前活跃的 Linux 应用
    
    Returns:
        "wps": WPS 文字
        "wps_excel": WPS 表格
        "": 未识别
    """
    # 方法 1: 使用 xdotool 获取前台窗口
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=1
        )
        window_name = result.stdout.strip()
        
        if "WPS 文字" in window_name or "WPS Writer" in window_name:
            return "wps"
        elif "WPS 表格" in window_name or "ET" in window_name:
            return "wps_excel"
    
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    # 方法 2: 使用 wmctrl 获取窗口列表
    try:
        result = subprocess.run(
            ["wmctrl", "-l"],
            capture_output=True,
            text=True,
            timeout=1
        )
        
        for line in result.stdout.splitlines():
            if "wps" in line.lower():
                if "et" in line.lower():
                    return "wps_excel"
                return "wps"
    
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return ""


def get_frontmost_window_title() -> str:
    """获取前台窗口标题"""
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=1
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
```

### 4.5 Linux 剪贴板支持

```python
# pastemd/utils/linux/clipboard.py

import subprocess
from typing import Optional

try:
    import xclip
    _HAS_XCLIP = True
except ImportError:
    _HAS_XCLIP = False


def get_clipboard_html() -> str:
    """
    获取剪贴板 HTML 内容
    
    Returns:
        HTML 字符串，如果不存在返回空字符串
    """
    if _HAS_XCLIP:
        try:
            return xclip.paste(selection="clipboard", target="text/html")
        except Exception:
            pass
    
    # 备用方案：使用 xclip 命令行
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "text/html", "-o"],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return ""


def copy_to_clipboard(text: str) -> None:
    """复制文本到剪贴板"""
    try:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
            timeout=1
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def simulate_paste() -> None:
    """
    模拟 Ctrl+V 粘贴
    
    注意：需要在有焦点的窗口中执行
    """
    try:
        subprocess.run(
            ["xdotool", "key", "ctrl+v"],
            timeout=1
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
```

---

## 5. Linux 托盘图标方案

### 5.1 方案概述

Linux 托盘图标实现面临碎片化问题，不同桌面环境使用不同的托盘协议。

**核心策略**: 使用 `pystray` 库，通过环境变量选择后端，优先使用 AppIndicator，兼容 X11 会话。

### 5.2 pystray 后端支持

| 后端 | 推荐度 | 功能完整度 | 依赖 | 兼容性 |
|------|--------|-----------|------|--------|
| **appindicator** | ⭐⭐⭐⭐⭐ | 90% | libappindicator3 | GNOME/KDE/Xfce/OpenBox |
| **gtk** | ⭐⭐⭐⭐ | 100% | PyGObject | 通用 GTK 环境 |
| **xorg** | ⭐⭐⭐ | 50% | 无 | X11 所有环境 |

```python
# pastemd/presentation/tray/linux_icon.py

import os
import pystray
from PIL import Image
from typing import Optional

class LinuxTrayIcon:
    """Linux 托盘图标管理器"""
    
    def __init__(self):
        self._icon: Optional[pystray.Icon] = None
        self._backend: str = ""
        self._detect_backend()
    
    def _detect_backend(self) -> None:
        """检测可用的托盘后端"""
        # 1. 优先使用环境变量设置
        if "PYSTRAY_BACKEND" in os.environ:
            self._backend = os.environ["PYSTRAY_BACKEND"]
            return
        
        # 2. 检测桌面环境
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        
        if "gnome" in desktop or "unity" in desktop:
            self._backend = "appindicator"
        elif "kde" in desktop:
            self._backend = "appindicator"
        elif "xfce" in desktop:
            self._backend = "appindicator"
        elif "openbox" in desktop:
            # OpenBox + Tint2 优先 appindicator
            self._backend = "appindicator"
        else:
            # 兜底使用 appindicator
            self._backend = "appindicator"
    
    def create_icon(self, icon_data: bytes, menu) -> pystray.Icon:
        """
        创建托盘图标
        
        Args:
            icon_data: PNG 图标数据
            menu: pystray.Menu 对象
        
        Returns:
            pystray.Icon 实例
        """
        image = Image.open(io.BytesIO(icon_data))
        
        self._icon = pystray.Icon(
            "pastemd",
            icon=image,
            title="PasteMD",
            menu=menu
        )
        
        # 设置后端
        if self._backend:
            os.environ["PYSTRAY_BACKEND"] = self._backend
        
        return self._icon
    
    def run(self) -> None:
        """运行托盘图标主循环"""
        if self._icon:
            self._icon.run()
    
    def stop(self) -> None:
        """停止托盘图标"""
        if self._icon:
            self._icon.stop()
    
    def update_icon(self, icon_data: bytes) -> None:
        """更新图标"""
        if self._icon:
            image = Image.open(io.BytesIO(icon_data))
            self._icon.icon = image
```

### 5.3 轻量级桌面环境支持

#### 5.3.1 OpenBox + Tint2 + PCManFM

Tint2 原生支持 **XEmbed** 系统托盘：

```ini
# ~/.config/tint2/tint2rc

# 启用系统托盘
systray = 1
systray_monitor = 1
systray_rectangle = 0 0 0 0
systray_sort = right2left
systray_icon_size = 24
systray_padding = 2
```

**兼容性**: ✅ pystray 的 appindicator 后端在 Tint2 下正常工作

#### 5.3.2 X11 会话要求

```bash
# 确保使用 X11 会话而非 Wayland
# 登录时选择 "OpenBox" 或 "OpenBox (X11)"

# 检查当前会话
echo $XDG_SESSION_TYPE
# 应该输出: x11
```

### 5.4 安装依赖

```bash
# Debian/Ubuntu/UOS/银河麒麟
sudo apt-get install -y \
    libappindicator3-1 \
    gir1.2-appindicator3-0.1 \
    libcairo2-dev \
    libgirepository1.0-dev \
    python3-gi \
    gir1.2-gtk-3.0

# Arch Linux
sudo pacman -S -y \
    libappindicator-gtk3 \
    python-gobject \
    python-pillow

# Fedora
sudo dnf install -y \
    libappindicator-gtk3 \
    python3-gobject \
    python3-pillow
```

### 5.5 多桌面环境兼容性矩阵

| 桌面环境 | 推荐后端 | 托盘插件 | 状态 |
|---------|---------|---------|------|
| **GNOME 40+** | appindicator | AppIndicator 扩展 | ✅ |
| **KDE Plasma** | appindicator | 原生支持 | ✅ |
| **Xfce 4.16+** | appindicator | 面板插件 | ✅ |
| **Cinnamon** | appindicator | 面板小程序 | ✅ |
| **MATE** | appindicator | 面板指示器 | ✅ |
| **OpenBox + Tint2** | appindicator | systray | ✅ |
| **i3 + polybar** | xorg | 自定义模块 | ⚠️ |
| **Wayland** | 有限 | 需 SNI | ⚠️ |

### 5.6 备选方案：Qt QSystemTrayIcon

如果 pystray 不可用，可使用 Qt：

```python
# pastemd/presentation/tray/qt_tray.py

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

class QtTrayIcon:
    """Qt 托盘图标实现"""
    
    def __init__(self, app):
        self._app = app
        self._tray = QSystemTrayIcon()
        
        # 设置图标
        icon = QIcon("assets/icons/logo.png")
        self._tray.setIcon(icon)
        self._tray.setVisible(True)
        
        # 创建菜单
        self._menu = QMenu()
        self._setup_menu()
        self._tray.setContextMenu(self._menu)
    
    def _setup_menu(self):
        """设置菜单"""
        self._menu.addAction("设置", self._open_settings)
        self._menu.addSeparator()
        self._menu.addAction("退出", self._quit)
    
    def _open_settings(self):
        """打开设置"""
        # 实现设置窗口
        pass
    
    def _quit(self):
        """退出应用"""
        self._app.quit()
```

### 5.7 信创系统兼容性

| 系统 | 桌面环境 | 推荐后端 | 状态 |
|------|---------|---------|------|
| **UOS** | DDE | appindicator | ✅ |
| **银河麒麟** | UKUI | appindicator | ✅ |
| **openKylin** | UKUI | appindicator | ✅ |
| **麒麟V10** | UKUI | appindicator | ✅ |

### 5.8 降级策略

```python
# pastemd/presentation/tray/fallback.py

import subprocess
import os

def check_tray_availability() -> dict:
    """
    检查托盘可用性
    
    Returns:
        dict: {
            'pystray': bool,
            'appindicator': bool,
            'xorg': bool,
            'recommendation': str
        }
    """
    result = {
        'pystray': False,
        'appindicator': False,
        'xorg': False,
        'recommendation': 'text'
    }
    
    # 检查 pystray
    try:
        import pystray
        result['pystray'] = True
    except ImportError:
        return result
    
    # 检查 appindicator 后端
    try:
        proc = subprocess.run(
            ["python", "-c", "import gi; gi.require_version('AppIndicator3', '0.1')"],
            capture_output=True
        )
        if proc.returncode == 0:
            result['appindicator'] = True
    except Exception:
        pass
    
    # 检查 X11 会话
    if os.environ.get("XDG_SESSION_TYPE") == "x11":
        result['xorg'] = True
    
    # 推荐策略
    if result['appindicator']:
        result['recommendation'] = 'appindicator'
    elif result['xorg']:
        result['recommendation'] = 'xorg'
    else:
        result['recommendation'] = 'text_only'  # 纯文本模式
    
    return result
```

---

## 6. 技术实现路线图

### 6.1 实现阶段划分

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        PasteMD Linux 支持实现路线图                         │
└──────────────────────────────────────────────────────────────────────────┘

阶段 1: 基础架构 (第 1-2 周)
├──────────────────────────────────────────────────────────────────────────┤
│ 任务:                                                                  │
│  [ ] 创建 pastemd/utils/linux/ 目录结构                                  │
│  [ ] 创建 pastemd/service/document/linux/ 目录结构                        │
│  [ ] 创建 pastemd/service/spreadsheet/linux/ 目录结构                      │
│  [ ] 添加 pywpsrpc 到 requirements.txt                                   │
│  [ ] 校验并接入现有 system_detect.py 的 is_linux() 检查                  │
└──────────────────────────────────────────────────────────────────────────┘

阶段 2: 剪贴板支持 (第 2-3 周)
├──────────────────────────────────────────────────────────────────────────┤
│ 任务:                                                                  │
│  [ ] 实现 utils/linux/clipboard.py                                       │
│  [ ] 实现 HTML 剪贴板读取 (xclip/wayland-clipboard)                       │
│  [ ] 实现剪贴板文本读写                                                   │
│  [ ] 实现模拟粘贴 (xdotool)                                              │
│  [ ] 添加 xclip/xdotool 依赖检查                                         │
└──────────────────────────────────────────────────────────────────────────┘

阶段 3: WPS 文字集成 (第 3-4 周)
├──────────────────────────────────────────────────────────────────────────┤
│ 任务:                                                                  │
│  [ ] 实现 service/document/linux/wps.py                                  │
│  [ ] 实现 service/document/linux/wps_inserter.py                         │
│  [ ] 实现 DOCX 内容复制到 WPS                                            │
│  [ ] 实现文本直接插入                                                     │
│  [ ] 测试 WPS 文字各种场景                                               │
└──────────────────────────────────────────────────────────────────────────┘

阶段 4: WPS 表格集成 (第 4-5 周)
├──────────────────────────────────────────────────────────────────────────┤
│ 任务:                                                                  │
│  [ ] 实现 service/spreadsheet/linux/wps_excel.py                         │
│  [ ] 实现表格数据粘贴                                                    │
│  [ ] 测试 WPS 表格各种场景                                              │
└──────────────────────────────────────────────────────────────────────────┘

阶段 5: 应用检测与路由 (第 5 周)
├──────────────────────────────────────────────────────────────────────────┤
│ 任务:                                                                  │
│  [ ] 实现 utils/linux/detector.py                                        │
│  [ ] 更新 workflows/router.py 添加 Linux 路由                            │
│  [ ] 测试应用检测各种场景                                                │
└──────────────────────────────────────────────────────────────────────────┘

阶段 6: 系统通知与打磨 (第 6 周)
├──────────────────────────────────────────────────────────────────────────┤
│ 任务:                                                                  │
│  [ ] 实现 notification/linux/ 目录 (notify-send)                         │
│  [ ] 更新托盘菜单支持 Linux                                              │
│  [ ] 修复桌面环境兼容性问题                                              │
│  [ ] 编写单元测试                                                        │
│  [ ] 编写集成测试                                                        │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.2 依赖项清单

#### 6.2.1 Python 依赖

```txt
# requirements.txt 新增

# Linux 平台依赖
pywpsrpc>=1.0.0        # WPS Office RPC API
```

#### 6.2.2 系统依赖

```bash
# Debian/Ubuntu
sudo apt-get install -y \
    xclip \
    xdotool \
    wmctrl \
    libnotify-bin \
    qt5-default

# Arch Linux
sudo pacman -S \
    xclip \
    xdotool \
    wmctrl \
    libnotify \
    qt5-base

# Fedora
sudo dnf install \
    xclip \
    xdotool \
    wmctrl \
    notify-python \
    qt5-qtbase-devel
```

### 6.3 代码改动清单

#### 6.3.1 新增文件

```
新增文件:
├── pastemd/utils/linux/
│   ├── __init__.py
│   ├── clipboard.py          # Linux 剪贴板实现
│   ├── detector.py           # Linux 应用检测
│   └── keystroke.py          # 模拟按键
│
├── pastemd/service/document/linux/
│   ├── __init__.py
│   ├── wps.py                # WPS 落地器
│   └── wps_inserter.py       # WPS 插入器
│
├── pastemd/service/spreadsheet/linux/
│   ├── __init__.py
│   └── wps_excel.py          # WPS 表格落地器
│
└── pastemd/service/notification/linux/
    ├── __init__.py
    └── notify_send.py        # notify-send 通知
```

#### 6.3.2 修改文件

```python
# pastemd/utils/system_detect.py (修改)

def is_linux() -> bool:
    return get_os_name() == "linux"


# pastemd/utils/detector.py (修改)

if sys.platform == "linux":
    from .linux.detector import (
        detect_active_app as _detect_active_app,
        detect_wps_type as _detect_wps_type,
    )
    from .linux.detector import (
        get_frontmost_window_title as _get_frontmost_window_title,
    )


# pastemd/utils/clipboard.py (修改)

elif sys.platform == "linux":
    from .linux.clipboard import (
        get_clipboard_text,
        set_clipboard_text,
        is_clipboard_empty,
        is_clipboard_html,
        get_clipboard_html,
        set_clipboard_rich_text,
        copy_files_to_clipboard,
        is_clipboard_files,
        get_clipboard_files,
        preserve_clipboard,
    )
    from .linux.keystroke import simulate_paste
    from .clipboard_file_utils import read_file_with_encoding


# pastemd/app/workflows/router.py (修改)

elif sys.platform == "linux":
    from .linux import WPSWorkflow, WPSExcelWorkflow
```

---

## 7. 风险与挑战

### 7.1 技术风险

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| WPS Linux 安装量少 | 中 | 提供 WPS 纯剪贴板兜底方案 |
| pywpsrpc 稳定性 | 中 | 添加超时和重试机制 |
| Wayland 兼容性 | 高 | 同时支持 X11 和 Wayland |
| 桌面环境差异 | 中 | 使用 D-Bus 接口抽象 |

### 7.2 环境依赖风险

```
依赖链:
    PasteMD
        │
        ├─→ pywpsrpc
        │       │
        │       └─→ WPS Office Linux (11.1.0.9080+)
        │               │
        │               └─→ Qt5 运行时
        │                       │
        │                       └─→ 桌面环境 (X11/Wayland)
        │
        └─→ xclip/xdotool
                │
                └─→ X11 窗口系统
```

### 7.3 兼容性矩阵

| 组件 | Ubuntu | Debian | Fedora | Arch | openSUSE |
|------|--------|--------|--------|------|----------|
| WPS Office | ✅ | ✅ | ✅ | ✅ | ✅ |
| pywpsrpc | ✅ | ✅ | ✅ | ✅ | ✅ |
| xclip | ✅ | ✅ | ✅ | ✅ | ✅ |
| xdotool | ✅ | ✅ | ✅ | ✅ | ✅ |
| notify-send | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 8. 总结与建议

### 8.1 可行性结论

| 评估项 | 结论 | 说明 |
|--------|------|------|
| **技术可行性** | ✅ 完全可行 | pywpsrpc 提供完整 RPC API |
| **实现复杂度** | ⚠️ 中等 | 需要处理多种桌面环境 |
| **维护成本** | ⚠️ 中等 | 新增平台代码需要持续测试 |
| **用户价值** | ✅ 高 | 覆盖 Linux WPS 用户 |

### 8.2 推荐实现策略

```
优先级排序:

1. WPS Linux 文字 (pywpsrpc rpcwpsapi)
   └─ 文档内容插入是核心功能
   
2. WPS Linux 表格 (pywpsrpc rpcetapi)
   └─ 表格数据粘贴
   
3. 富文本剪贴板 (xclip/wayland)
   └─ HTML 内容读取
   
4. 系统通知 (notify-send)
   └─ 操作反馈
```

### 8.3 备选方案

如果 `pywpsrpc` 不可用或不稳定，可考虑 WPS 场景内降级：

#### 8.3.1 纯剪贴板方案

```python
# 如果无法集成 WPS RPC，则使用剪贴板 + 模拟粘贴

def paste_via_clipboard(content):
    # 1. 复制到剪贴板
    copy_to_clipboard(content)
    
    # 2. 模拟 Ctrl+V
    simulate_paste()
```

### 8.4 未来扩展方向

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         未来扩展路线                                      │
└──────────────────────────────────────────────────────────────────────────┘

近期 (1-3 个月):
├─ [ ] Linux 基础功能稳定
├─ [ ] 完善错误处理和日志
└─ [ ] 添加自动化测试

中期 (3-6 个月):
├─ [ ] WPS 高级格式化支持
├─ [ ] WPS 稳定性与兼容性增强
└─ [ ] 插件系统

远期 (6 个月+):
├─ [ ] Wayland 原生支持
├─ [ ] 平板/触控支持
└─ [ ] 云端协作功能
```

---

## 9. 附录

### 9.1 参考资料

| 资源 | 链接 |
|------|------|
| pywpsrpc GitHub | https://github.com/timxx/pywpsrpc |
| WPS 开放平台 | https://open.wps.cn/docs/office |
| VBA API 文档 | https://docs.microsoft.com/en-us/office/vba/api/overview |
| xclip 文档 | https://github.com/astrand/xclip |
| xdotool 文档 | https://www.semicomplete.com/projects/xdotool |

### 9.2 相关项目

| 项目 | 说明 |
|------|------|
| wpsrpc-sdk | WPS Office Linux RPC SDK C++ 版 |
| wps-office-all-lang | WPS Office 多语言版本打包 |

### 9.3 术语表

| 术语 | 定义 |
|------|------|
| RPC | Remote Procedure Call，远程过程调用 |
| pywpsrpc | Python bindings for WPS Office RPC |
| COM | Component Object Model，Windows 组件对象模型 |
| Qt5 | 跨平台 GUI 工具包 |
| X11 | X Window System 第11版 |
| Wayland | X11 的现代替代显示服务器协议 |

---

## 修订历史

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| 1.1 | 2026-02-17 | 修订错误并移除 LibreOffice 集成方案（仅保留 WPS 支持） | PasteMD Team |
| 1.0 | 2026-02-10 | 初始版本 | PasteMD Team |

---

*本文档由 PasteMD Architecture Team 生成*
