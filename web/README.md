# WebView 界面验证

这个目录用于验证使用 `pywebview` 构建 PasteMD 界面的可行性。

## 快速开始

### 1. 安装依赖

**Windows:**
```bash
pip install pywebview
```

**macOS:**
```bash
pip install pywebview pyobjc pyobjc-framework-Cocoa pyobjc-framework-WebKit
```

### 2. 运行示例

```bash
python web/demo.py
```

### 3. macOS 环境检测

```bash
python web/check_macos.py
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `demo.py` | WebView 主程序，包含 Python API 类（跨平台） |
| `index.html` | 设置界面的 HTML/CSS/JS |
| `check_macos.py` | macOS 环境检测脚本 |

## 跨平台支持

### Windows ✅ 已验证

- **渲染引擎**: EdgeChromium (推荐) / MSHTML / CEF
- **依赖**: `pip install pywebview`
- **状态**: 完全支持

### macOS 📋 待验证

- **渲染引擎**: WebKit (Cocoa)
- **依赖**: `pip install pywebview pyobjc pyobjc-framework-Cocoa pyobjc-framework-WebKit`
- **注意事项**:
  - WebView 必须在主线程启动
  - 与 pystray 托盘集成需要特殊处理
  - 打包为 .app 时需要配置 Info.plist

### macOS 特殊考虑

1. **主线程限制**
   ```python
   # macOS 的 Cocoa 要求 UI 在主线程运行
   # pywebview 会自动处理，但与其他 GUI 库集成时需注意
   ```

2. **与 pystray 集成**
   ```python
   # 方案 A: pystray 在后台线程，webview 在主线程
   # 方案 B: 使用 rumps 替代 pystray (macOS 原生)
   ```

3. **打包注意事项**
   ```bash
   # 使用 py2app 打包
   pip install py2app
   python setup.py py2app
   ```

## pywebview 特性验证

### ✅ 已验证功能 (Windows)

- [x] 创建原生窗口
- [x] 加载本地 HTML 文件
- [x] Python 暴露 API 给 JavaScript (`js_api`)
- [x] JavaScript 调用 Python 方法 (`window.pywebview.api.xxx`)
- [x] Python 调用 JavaScript (`window.evaluate_js()`)
- [x] 窗口配置 (大小、标题、背景色)
- [x] 热键录制交互

### 📋 待测试功能

- [ ] macOS 基础运行
- [ ] macOS 与 pystray 集成
- [ ] 多窗口管理
- [ ] 文件选择对话框
- [ ] 打包后的表现 (PyInstaller / py2app)

## 技术要点

### Python → JavaScript 通信

```python
# demo.py
class Api:
    def get_settings(self) -> str:
        return json.dumps(self.settings)

# 创建窗口时传入 js_api
window = webview.create_window(..., js_api=Api())
```

### JavaScript → Python 通信

```javascript
// index.html
window.addEventListener('pywebviewready', async () => {
    const result = await window.pywebview.api.get_settings();
    console.log(result);
});
```

### 渲染引擎选择

pywebview 会自动选择最佳渲染引擎：
- **Windows**: EdgeChromium (推荐) / MSHTML / CEF
- **macOS**: WebKit (Cocoa)
- **Linux**: WebKitGTK / CEF

## 与当前 tkinter 方案对比

| 特性 | tkinter | pywebview |
|------|---------|-----------|
| 界面美观度 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 开发效率 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 依赖大小 | 0 (内置) | ~10MB |
| 动画/过渡 | ❌ | ✅ CSS |
| 主题自定义 | 困难 | 容易 |
| 跨平台一致性 | 一般 | 好 |
| 学习曲线 | Python | HTML/CSS/JS |
| macOS 主线程 | 需处理 | 需处理 |

## macOS 验证清单

在 macOS 上运行前，请确认：

- [ ] Python 3.8+ 已安装
- [ ] pywebview 已安装 (`pip install pywebview`)
- [ ] PyObjC 已安装 (`pip install pyobjc`)
- [ ] 运行 `python web/check_macos.py` 检测环境
- [ ] 运行 `python web/demo.py` 验证基础功能

## 结论

pywebview 非常适合 PasteMD 的设置界面改造：

1. **更现代的 UI** - 可以使用任意 CSS 框架
2. **开发效率高** - Web 技术栈成熟，调试方便
3. **维护成本低** - HTML/CSS 比 tkinter 布局更直观
4. **用户体验好** - 支持动画、过渡、响应式设计
5. **跨平台一致** - Windows/macOS 渲染效果一致

### macOS 集成建议

1. 优先验证 `demo.py` 在 macOS 上的基础运行
2. 测试与现有 pystray 托盘的集成方案
3. 考虑使用 `rumps` 替代 `pystray` 作为 macOS 托盘方案
