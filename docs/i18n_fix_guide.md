# WebView多语言Bug修复指南

## Bug诊断总结

经过系统分析，发现webview界面多语言实现存在以下严重问题：

1. **Bug 1**: `get_translations()` 缺失15个翻译键
2. **Bug 2**: JavaScript中使用的11个键未在`get_translations()`中返回
3. **Bug 3**: HTML中存在83处硬编码的中文文本
4. **Bug 4**: 语言切换后前端界面不刷新
5. **Bug 5**: 动态内容（语言列表、动作列表）不会在语言切换后更新

---

## 修复方案

### 修复1: 补全 `get_translations()` 中的缺失键

**文件**: `pastemd/presentation/webview/api/settings.py`

**位置**: 第259-340行的 `get_translations()` 方法

**需要添加的键**:

```python
def get_translations(self) -> str:
    """获取当前语言的常用翻译文本"""
    try:
        # 返回常用的翻译键
        translations = {
            # 设置对话框
            "settings.dialog.title": t("settings.dialog.title"),
            "settings.buttons.save": t("settings.buttons.save"),
            "settings.buttons.cancel": t("settings.buttons.cancel"),

            # 选项卡
            "settings.tab.general": t("settings.tab.general"),
            "settings.tab.conversion": t("settings.tab.conversion"),
            "settings.tab.advanced": t("settings.tab.advanced"),
            "settings.tab.experimental": t("settings.tab.experimental"),
            "settings.tab.permissions": t("settings.tab.permissions"),

            # 常规设置
            "settings.general.save_dir": t("settings.general.save_dir"),
            "settings.general.browse": t("settings.general.browse"),
            "settings.general.restore_default": t("settings.general.restore_default"),
            "settings.general.no_app_action": t("settings.general.no_app_action"),
            "settings.general.keep_file": t("settings.general.keep_file"),
            "settings.general.notify": t("settings.general.notify"),
            "settings.general.startup_notify": t("settings.general.startup_notify"),
            "settings.general.move_cursor": t("settings.general.move_cursor"),
            "settings.general.hotkey": t("settings.general.hotkey"),
            "settings.general.set_hotkey": t("settings.general.set_hotkey"),
            "settings.general.language": t("settings.general.language"),

            # 转换设置
            "settings.conversion.pandoc_path": t("settings.conversion.pandoc_path"),
            "settings.conversion.reference_docx": t("settings.conversion.reference_docx"),
            "settings.general.clear": t("settings.general.clear"),
            "settings.conversion.pandoc_filters": t("settings.conversion.pandoc_filters"),
            "settings.conversion.add_filter": t("settings.conversion.add_filter"),
            "settings.conversion.remove_filter": t("settings.conversion.remove_filter"),
            "settings.conversion.move_up": t("settings.conversion.move_up"),
            "settings.conversion.move_down": t("settings.conversion.move_down"),
            "settings.conversion.pandoc_filters_note": t("settings.conversion.pandoc_filters_note"),
            "settings.conversion.html_formatting": t("settings.conversion.html_formatting"),
            "settings.conversion.strikethrough": t("settings.conversion.strikethrough"),
            "settings.conversion.first_paragraph_heading": t("settings.conversion.first_paragraph_heading"),
            "settings.conversion.md_indent": t("settings.conversion.md_indent"),
            "settings.conversion.html_indent": t("settings.conversion.html_indent"),

            # 高级设置
            "settings.advanced.excel_enable": t("settings.advanced.excel_enable"),
            "settings.advanced.excel_format": t("settings.advanced.excel_format"),

            # 实验性功能
            "settings.conversion.keep_formula": t("settings.conversion.keep_formula"),
            "settings.conversion.enable_latex_replacements": t("settings.conversion.enable_latex_replacements"),
            "settings.conversion.latex_replacements_note": t("settings.conversion.latex_replacements_note"),
            "settings.conversion.fix_single_dollar_block": t("settings.conversion.fix_single_dollar_block"),
            "settings.conversion.fix_single_dollar_block_note": t("settings.conversion.fix_single_dollar_block_note"),
            "settings.conversion.pandoc_request_headers": t("settings.conversion.pandoc_request_headers"),
            "settings.conversion.pandoc_request_headers_enable": t("settings.conversion.pandoc_request_headers_enable"),
            "settings.conversion.pandoc_request_headers_note": t("settings.conversion.pandoc_request_headers_note"),
            "settings.conversion.pandoc_request_headers_fill_example": t("settings.conversion.pandoc_request_headers_fill_example"),

            # 消息
            "settings.success.saved": t("settings.success.saved"),
            "settings.title.success": t("settings.title.success"),
            "settings.title.error": t("settings.title.error"),

            # 热键对话框
            "hotkey.dialog.title": t("hotkey.dialog.title"),
            "hotkey.dialog.current_hotkey": t("hotkey.dialog.current_hotkey"),
            "hotkey.dialog.new_hotkey": t("hotkey.dialog.new_hotkey"),
            "hotkey.dialog.record_button": t("hotkey.dialog.record_button"),
            "hotkey.dialog.recording_button": t("hotkey.dialog.recording_button"),
            "hotkey.dialog.record_again": t("hotkey.dialog.record_again"),
            "hotkey.dialog.waiting_input": t("hotkey.dialog.waiting_input"),
            "hotkey.dialog.cancel_button": t("hotkey.dialog.cancel_button"),
            "hotkey.dialog.save_button": t("hotkey.dialog.save_button"),

            # ========== 新增：权限相关 ==========
            "settings.permissions.intro": t("settings.permissions.intro"),
            "settings.permissions.add_hint": t("settings.permissions.add_hint"),
            "settings.permissions.refresh": t("settings.permissions.refresh"),
            "settings.permissions.last_checked": t("settings.permissions.last_checked"),
            "settings.permissions.open_settings": t("settings.permissions.open_settings"),
            "settings.permissions.request_access": t("settings.permissions.request_access"),
            "settings.permissions.status.checking": t("settings.permissions.status.checking"),
            "settings.permissions.accessibility.title": t("settings.permissions.accessibility.title"),
            "settings.permissions.accessibility.desc": t("settings.permissions.accessibility.desc"),
            "settings.permissions.screen_recording.title": t("settings.permissions.screen_recording.title"),
            "settings.permissions.screen_recording.desc": t("settings.permissions.screen_recording.desc"),
            "settings.permissions.input_monitoring.title": t("settings.permissions.input_monitoring.title"),
            "settings.permissions.input_monitoring.desc": t("settings.permissions.input_monitoring.desc"),
            "settings.permissions.automation.title": t("settings.permissions.automation.title"),
            "settings.permissions.automation.desc": t("settings.permissions.automation.desc"),

            # ========== 新增：JavaScript中使用的键 ==========
            "settings.error.init_failed": t("settings.error.init_failed"),
            "settings.error.load_failed": t("settings.error.load_failed"),
            "settings.error.save_failed": t("settings.error.save_failed"),
            "settings.error.hotkey_save_failed": t("settings.error.hotkey_save_failed"),
            "settings.error.hotkey_not_recorded": t("settings.error.hotkey_not_recorded"),
            "settings.success.hotkey_saved": t("settings.success.hotkey_saved"),
        }

        return self._success(translations)
    except Exception as e:
        log(f"Failed to get translations: {e}")
        return self._error(str(e), "GET_TRANSLATIONS_ERROR")
```

---

### 修复2: 添加缺失的locale键

**文件**: `pastemd/i18n/locales/zh-CN.json`

**需要添加的键**:

```json
{
    // ... 现有内容 ...

    "settings.error.init_failed": "初始化失败: {error}",
    "settings.error.load_failed": "加载设置失败",
    "settings.error.save_failed": "保存失败: {error}",
    "settings.error.hotkey_save_failed": "保存热键失败: {error}",
    "settings.error.hotkey_not_recorded": "请先录制热键",
    "settings.success.hotkey_saved": "热键已保存"
}
```

**文件**: `pastemd/i18n/locales/en-US.json`

**需要添加的键**:

```json
{
    // ... 现有内容 ...

    "settings.error.init_failed": "Initialization failed: {error}",
    "settings.error.load_failed": "Failed to load settings",
    "settings.error.save_failed": "Save failed: {error}",
    "settings.error.hotkey_save_failed": "Failed to save hotkey: {error}",
    "settings.error.hotkey_not_recorded": "Please record a hotkey first",
    "settings.success.hotkey_saved": "Hotkey saved"
}
```

---

### 修复3: 添加语言切换通知机制

**文件**: `pastemd/presentation/webview/api/settings.py`

**修改 `save_settings()` 方法**:

```python
def save_settings(self, settings_json: str) -> str:
    """保存设置"""
    try:
        new_settings = json.loads(settings_json)

        # ... 现有保存逻辑 ...

        # 更新语言
        language_changed = False
        if "language" in new_settings:
            old_language = app_state.config.get("language", FALLBACK_LANGUAGE)
            new_language = new_settings["language"]
            if old_language != new_language:
                language_changed = True
                set_language(new_language)

        # ... 现有保存逻辑 ...

        # 如果语言改变了，通知前端刷新
        if language_changed and self._window:
            def notify_language_change():
                try:
                    self._window.evaluate_js("window.onLanguageChanged && window.onLanguageChanged()")
                except Exception as e:
                    log(f"Failed to notify language change: {e}")
            app_state.queue_ui_task(notify_language_change)

        log("Settings saved successfully")
        return self._success(message=t("settings.success.saved"))
    except Exception as e:
        log(f"Failed to save settings: {e}")
        return self._error(str(e), "SAVE_ERROR")
```

---

### 修复4: 添加前端语言切换处理

**文件**: `pastemd/presentation/webview/assets/js/main.js`

**添加语言切换处理函数**:

```javascript
/**
 * 语言切换处理
 */
window.onLanguageChanged = async function() {
    try {
        console.log('Language changed, reloading translations...');

        // 重新加载翻译
        await window.i18n.load();

        // 重新加载语言列表
        await loadLanguages();

        // 重新加载动作列表
        await loadNoAppActions();

        // 更新界面
        window.i18n.updateAllElements();

        console.log('Language change completed');
    } catch (e) {
        console.error('Failed to handle language change:', e);
    }
};

/**
 * 监听语言选择框变化
 */
document.addEventListener('DOMContentLoaded', function() {
    const languageSelect = document.getElementById('language');
    if (languageSelect) {
        languageSelect.addEventListener('change', async function() {
            // 语言切换会在保存设置时触发，这里只是预览
            // 实际切换在用户点击"保存"按钮后生效
            console.log('Language selection changed to:', this.value);
        });
    }
});
```

---

### 修复5: 修复JavaScript中的硬编码文本

**文件**: `pastemd/presentation/webview/assets/js/main.js`

**替换硬编码的中文文本**:

```javascript
// 第60行
showToast('初始化失败: ' + e.message, 'error');
// 改为:
showToast(t('settings.error.init_failed', { error: e.message }), 'error');

// 第89行
showToast('加载设置失败', 'error');
// 改为:
showToast(t('settings.error.load_failed'), 'error');

// 第247行
showToast('保存失败: ' + e.message, 'error');
// 改为:
showToast(t('settings.error.save_failed', { error: e.message }), 'error');

// 第342行
showToast('请先录制热键', 'warning');
// 改为:
showToast(t('settings.error.hotkey_not_recorded'), 'warning');

// 第362行
showToast('热键已保存');
// 改为:
showToast(t('settings.success.hotkey_saved'));

// 第367行
showToast('保存热键失败: ' + e.message, 'error');
// 改为:
showToast(t('settings.error.hotkey_save_failed', { error: e.message }), 'error');
```

---

### 修复6: 移除HTML中的硬编码文本

**文件**: `pastemd/presentation/webview/assets/index.html`

**需要修改的位置**:

1. **第6行 - 页面标题**:
```html
<title>PasteMD 设置</title>
<!-- 改为: -->
<title data-i18n="settings.dialog.title">PasteMD 设置</title>
```

2. **第45行 - 选项标题**:
```html
<div class="section-title">选项</div>
<!-- 改为: -->
<div class="section-title" data-i18n="settings.general.options">选项</div>
```

3. **第156行 - Excel选项标题**:
```html
<div class="section-title">Excel 选项</div>
<!-- 改为: -->
<div class="section-title" data-i18n="settings.advanced.excel_options">Excel 选项</div>
```

4. **第171行 - 公式处理标题**:
```html
<div class="section-title">公式处理</div>
<!-- 改为: -->
<div class="section-title" data-i18n="settings.experimental.formula_processing">公式处理</div>
```

5. **第299行 - 热键录制说明**:
```html
<p style="margin-bottom: 16px;">点击"录制"按钮，然后按下您想要设置的快捷键组合。</p>
<!-- 改为: -->
<p style="margin-bottom: 16px;" data-i18n="hotkey.dialog.instruction">点击"录制"按钮，然后按下您想要设置的快捷键组合。</p>
```

6. **第104行 - 参考文档placeholder**:
```html
<input type="text" id="reference-docx" placeholder="可选：用于设置样式的参考 .docx 文件">
<!-- 改为: -->
<input type="text" id="reference-docx" data-i18n-placeholder="settings.conversion.reference_docx_placeholder">
```

7. **第194行 - 请求头placeholder**:
```html
<textarea id="request-headers" rows="4" placeholder="每行一个请求头，格式：Header-Name: value" disabled></textarea>
<!-- 改为: -->
<textarea id="request-headers" rows="4" data-i18n-placeholder="settings.conversion.pandoc_request_headers_placeholder" disabled></textarea>
```

8. **第308行 - 热键输入框placeholder**:
```html
<input type="text" id="hotkey-input" class="hotkey-input" readonly placeholder="点击录制...">
<!-- 改为: -->
<input type="text" id="hotkey-input" class="hotkey-input" readonly data-i18n-placeholder="hotkey.dialog.input_placeholder">
```

---

### 修复7: 添加缺失的locale键（HTML相关）

**文件**: `pastemd/i18n/locales/zh-CN.json`

```json
{
    // ... 现有内容 ...

    "settings.general.options": "选项",
    "settings.advanced.excel_options": "Excel 选项",
    "settings.experimental.formula_processing": "公式处理",
    "settings.conversion.reference_docx_placeholder": "可选：用于设置样式的参考 .docx 文件",
    "settings.conversion.pandoc_request_headers_placeholder": "每行一个请求头，格式：Header-Name: value",
    "hotkey.dialog.instruction": "点击"录制"按钮，然后按下您想要设置的快捷键组合。",
    "hotkey.dialog.input_placeholder": "点击录制..."
}
```

**文件**: `pastemd/i18n/locales/en-US.json`

```json
{
    // ... 现有内容 ...

    "settings.general.options": "Options",
    "settings.advanced.excel_options": "Excel Options",
    "settings.experimental.formula_processing": "Formula Processing",
    "settings.conversion.reference_docx_placeholder": "Optional: Reference .docx file for styling",
    "settings.conversion.pandoc_request_headers_placeholder": "One header per line, format: Header-Name: value",
    "hotkey.dialog.instruction": "Click the \"Record\" button, then press the key combination you want to set.",
    "hotkey.dialog.input_placeholder": "Click to record..."
}
```

---

## 修复优先级

| 优先级 | 修复项 | 影响范围 | 难度 |
|--------|--------|---------|------|
| P0 | 修复1: 补全 `get_translations()` | 所有权限相关UI | 简单 |
| P0 | 修复2: 添加缺失的locale键 | JavaScript错误提示 | 简单 |
| P0 | 修复3: 添加语言切换通知机制 | 语言切换功能 | 中等 |
| P0 | 修复4: 添加前端语言切换处理 | 语言切换功能 | 中等 |
| P1 | 修复5: 修复JavaScript硬编码文本 | 错误提示 | 简单 |
| P1 | 修复6: 移除HTML硬编码文本 | 多个UI元素 | 中等 |
| P1 | 修复7: 添加HTML相关locale键 | 多个UI元素 | 简单 |

---

## 测试步骤

1. 运行测试脚本验证修复:
```bash
python test/test_i18n_bugs.py
```

2. 启动应用并打开设置界面

3. 切换语言，验证:
   - 界面文本是否立即更新
   - 权限相关文本是否正确显示
   - 错误提示是否使用正确的语言

4. 测试各种操作，验证:
   - 热键录制
   - 文件选择
   - 设置保存
   - 权限检查

---

## 注意事项

1. 修复后需要重新打包应用才能看到效果
2. 语言切换需要保存设置后才会生效
3. 某些硬编码文本可能需要根据实际UI布局调整
4. 建议在修复后进行全面的回归测试