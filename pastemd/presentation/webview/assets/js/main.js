/**
 * PasteMD Settings - Main Application Logic
 * 主页面逻辑
 */

// 全局状态
const state = {
    settings: {},
    originalSettings: {},
    languages: [],
    noAppActions: [],
    themeOptions: [],
    platform: { is_windows: false, is_macos: false },
    filters: [],
    isDirty: false,
    selectedFilterIndex: -1
};

/**
 * 初始化应用
 */
async function initApp() {
    try {
        // 等待 API 就绪
        await window.api.waitReady();

        // 获取平台信息
        state.platform = await window.api.getPlatform();
        applyPlatformClasses();

        // 初始化平台视觉效果（Mica/Vibrancy）
        if (window.platformEffects) {
            window.platformEffects.init(state.platform);
        }

        // 加载翻译
        await window.i18n.load();

        // 初始化选项卡
        window.tabManager.init();

        // 加载设置
        await loadSettings();

        // 加载语言列表
        await loadLanguages();

        // 加载动作列表
        await loadNoAppActions();

        // 加载主题选项
        await loadThemeOptions();

        // 应用初始主题
        applyTheme(state.settings.theme || 'auto');

        // 设置系统主题变化监听
        setupSystemThemeListener();

        // 初始化热键录制器
        await window.hotkeyRecorder.init();

        // 初始化权限管理 (macOS)
        if (state.platform.is_macos) {
            await window.permissionsManager.init();
        }

        // 移除加载状态
        document.body.classList.remove('loading');
        document.body.classList.add('loaded');

        console.log('PasteMD Settings initialized');

    } catch (e) {
        console.error('Failed to initialize app:', e);
        showToast(t('settings.error.init_failed', { error: e.message }), 'error');
    }
}

/**
 * 应用平台相关的 CSS 类
 */
function applyPlatformClasses() {
    if (state.platform.is_macos) {
        document.body.classList.add('platform-macos');
    } else if (state.platform.is_windows) {
        document.body.classList.add('platform-windows');
    }
}

/**
 * 加载设置
 */
async function loadSettings() {
    try {
        state.settings = await window.api.getSettings();
        state.originalSettings = JSON.parse(JSON.stringify(state.settings));
        state.filters = state.settings.pandoc_filters || [];

        // 填充表单
        populateForm();

    } catch (e) {
        console.error('Failed to load settings:', e);
        showToast(t('settings.error.load_failed'), 'error');
    }
}

/**
 * 加载语言列表
 */
async function loadLanguages() {
    try {
        state.languages = await window.api.getLanguages();

        const select = document.getElementById('language');
        if (select) {
            select.innerHTML = '';
            state.languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang.code;
                option.textContent = lang.label;
                select.appendChild(option);
            });

            // 设置当前值
            select.value = state.settings.language || 'en-US';
        }
    } catch (e) {
        console.error('Failed to load languages:', e);
    }
}

/**
 * 加载无应用动作列表
 */
async function loadNoAppActions() {
    try {
        state.noAppActions = await window.api.getNoAppActions();

        const select = document.getElementById('no-app-action');
        if (select) {
            select.innerHTML = '';
            state.noAppActions.forEach(action => {
                const option = document.createElement('option');
                option.value = action.value;
                option.textContent = action.label;
                select.appendChild(option);
            });

            // 设置当前值
            select.value = state.settings.no_app_action || 'open';
        }
    } catch (e) {
        console.error('Failed to load no-app actions:', e);
    }
}

/**
 * 加载主题选项列表
 */
async function loadThemeOptions() {
    try {
        state.themeOptions = await window.api.getThemeOptions();

        const select = document.getElementById('theme');
        if (select) {
            select.innerHTML = '';
            state.themeOptions.forEach(theme => {
                const option = document.createElement('option');
                option.value = theme.value;
                option.textContent = theme.label;
                select.appendChild(option);
            });

            // 设置当前值
            select.value = state.settings.theme || 'auto';

            // 监听变化
            select.addEventListener('change', (e) => {
                applyTheme(e.target.value);
            });
        }
    } catch (e) {
        console.error('Failed to load theme options:', e);
    }
}

/**
 * 应用主题
 */
function applyTheme(theme) {
    const root = document.documentElement;
    root.classList.remove('auto-theme', 'light-theme', 'dark-theme');

    if (theme === 'auto') {
        root.classList.add('auto-theme');
    } else if (theme === 'light') {
        root.classList.add('light-theme');
    } else {
        root.classList.add('dark-theme');
    }

    // 通知平台效果管理器主题变化
    if (window.platformEffects) {
        window.platformEffects.onThemeChange(theme);
    }

    console.log('Theme applied:', theme);
}

/**
 * 设置系统主题变化监听
 */
function setupSystemThemeListener() {
    window.matchMedia('(prefers-color-scheme: dark)')
        .addEventListener('change', (e) => {
            // 只有在 auto 模式下才响应系统主题变化
            const currentTheme = state.settings.theme || 'auto';
            if (currentTheme === 'auto') {
                // CSS 媒体查询会自动处理，这里可以做额外的处理（如果需要）
                console.log('System theme changed, dark mode:', e.matches);
            }
        });
}

// 暴露给 Python 调用
window.onThemeChanged = function(theme) {
    applyTheme(theme);
};

/**
 * 填充表单
 */
function populateForm() {
    const s = state.settings;

    // 常规设置
    setInputValue('save-dir', s.save_dir || '');
    setCheckbox('keep-file', s.keep_file);
    setCheckbox('notify', s.notify);
    setCheckbox('startup-notify', s.startup_notify);
    setCheckbox('move-cursor', s.move_cursor_to_end);
    setInputValue('hotkey-display', formatHotkey(s.hotkey || '<ctrl>+<shift>+b'));

    // 转换设置
    setInputValue('pandoc-path', s.pandoc_path || 'pandoc');
    setInputValue('reference-docx', s.reference_docx || '');
    setCheckbox('strikethrough-to-del', s.html_formatting?.strikethrough_to_del ?? true);
    setCheckbox('md-disable-indent', s.md_disable_first_para_indent);
    setCheckbox('html-disable-indent', s.html_disable_first_para_indent);

    // 高级设置
    setCheckbox('enable-excel', s.enable_excel);
    setCheckbox('excel-keep-format', s.excel_keep_format);
    setCheckbox('debug-mode', s.debug_mode);

    // 实验性功能
    setCheckbox('keep-formula', s.Keep_original_formula);
    setCheckbox('enable-latex-replacements', s.enable_latex_replacements);
    setCheckbox('fix-single-dollar-block', s.fix_single_dollar_block);

    // Pandoc request headers
    const headers = s.pandoc_request_headers || [];
    const hasHeaders = headers.length > 0;
    setCheckbox('enable-request-headers', hasHeaders);
    setInputValue('request-headers', headers.join('\n'));
    toggleRequestHeadersState();

    // Filters 列表
    refreshFiltersList();
}

/**
 * 收集表单数据
 */
function collectFormData() {
    const settings = {
        // 常规设置
        language: getSelectValue('language'),
        theme: getSelectValue('theme'),
        save_dir: getInputValue('save-dir'),
        keep_file: getCheckbox('keep-file'),
        notify: getCheckbox('notify'),
        startup_notify: getCheckbox('startup-notify'),
        no_app_action: getSelectValue('no-app-action'),

        // 转换设置
        pandoc_path: getInputValue('pandoc-path'),
        reference_docx: getInputValue('reference-docx') || null,
        html_formatting: {
            strikethrough_to_del: getCheckbox('strikethrough-to-del')
        },
        md_disable_first_para_indent: getCheckbox('md-disable-indent'),
        html_disable_first_para_indent: getCheckbox('html-disable-indent'),

        // 高级设置
        enable_excel: getCheckbox('enable-excel'),
        excel_keep_format: getCheckbox('excel-keep-format'),
        debug_mode: getCheckbox('debug-mode'),

        // 实验性功能
        Keep_original_formula: getCheckbox('keep-formula'),
        enable_latex_replacements: getCheckbox('enable-latex-replacements'),
        fix_single_dollar_block: getCheckbox('fix-single-dollar-block'),

        // Pandoc filters
        pandoc_filters: state.filters,

        // Pandoc request headers
        pandoc_request_headers: getCheckbox('enable-request-headers')
            ? getInputValue('request-headers').split('\n').filter(h => h.trim())
            : []
    };

    // Windows 特有
    if (state.platform.is_windows) {
        settings.move_cursor_to_end = getCheckbox('move-cursor');
    }

    return settings;
}

/**
 * 保存设置
 */
async function saveSettings() {
    try {
        const settings = collectFormData();
        await window.api.saveSettings(settings);
        showToast(t('settings.success.saved'));

        // 更新原始设置
        state.originalSettings = JSON.parse(JSON.stringify(settings));
        state.isDirty = false;

    } catch (e) {
        console.error('Failed to save settings:', e);
        showToast(t('settings.error.save_failed', { error: e.message }), 'error');
    }
}

/**
 * 取消/关闭
 */
async function closeWindow() {
    try {
        await window.api.closeWindow();
    } catch (e) {
        console.error('Failed to close window:', e);
    }
}

// ==================== 热键相关 ====================

let hotkeyModalVisible = false;
let pendingHotkey = null;

async function openHotkeyModal() {
    const modal = document.getElementById('hotkey-modal');
    if (!modal) return;

    modal.classList.remove('hidden');
    hotkeyModalVisible = true;
    pendingHotkey = null;

    // 重置状态
    document.getElementById('hotkey-record-btn').disabled = false;
    document.getElementById('hotkey-record-btn').textContent = t('hotkey.dialog.record_button') || '录制';
    document.getElementById('hotkey-input').value = '';
    document.getElementById('hotkey-save-btn').disabled = true;

    // 获取并显示当前热键
    try {
        const result = await window.api.getCurrentHotkey();
        const currentHotkeyDisplay = document.getElementById('current-hotkey-display');
        if (currentHotkeyDisplay) {
            currentHotkeyDisplay.textContent = result.formatted || '--';
        }
    } catch (e) {
        console.error('Failed to get current hotkey:', e);
        const currentHotkeyDisplay = document.getElementById('current-hotkey-display');
        if (currentHotkeyDisplay) {
            currentHotkeyDisplay.textContent = '--';
        }
    }
}

function closeHotkeyModal() {
    const modal = document.getElementById('hotkey-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    hotkeyModalVisible = false;

    // 停止录制
    window.hotkeyRecorder.stop();
}

function startHotkeyRecording() {
    const input = document.getElementById('hotkey-input');
    const recordBtn = document.getElementById('hotkey-record-btn');

    recordBtn.disabled = true;
    recordBtn.textContent = t('hotkey.dialog.recording_button') || '录制中...';
    input.value = t('hotkey.dialog.waiting_input') || '请按下快捷键...';
    input.classList.add('recording');

    window.hotkeyRecorder.start(
        // onUpdate
        (displayText) => {
            input.value = displayText;
        },
        // onFinish
        (hotkeyStr, error) => {
            input.classList.remove('recording');
            recordBtn.disabled = false;
            recordBtn.textContent = t('hotkey.dialog.record_again') || '重新录制';

            if (error) {
                showToast(error, 'error');
                input.value = '';
            } else if (hotkeyStr) {
                pendingHotkey = hotkeyStr;
                input.value = formatHotkey(hotkeyStr);
                document.getElementById('hotkey-save-btn').disabled = false;
            }
        }
    );
}

async function saveHotkey() {
    if (!pendingHotkey) {
        showToast(t('settings.error.hotkey_not_recorded'), 'warning');
        return;
    }

    try {
        // 检查冲突
        const conflict = await window.api.checkHotkeyConflict(pendingHotkey);
        if (!conflict.is_available) {
            if (!confirm(t('hotkey.dialog.conflict_confirm'))) {
                return;
            }
        }

        // 保存
        await window.api.saveHotkey(pendingHotkey);

        // 更新显示
        document.getElementById('hotkey-display').value = formatHotkey(pendingHotkey);
        state.settings.hotkey = pendingHotkey;

        showToast(t('settings.success.hotkey_saved'));
        closeHotkeyModal();

    } catch (e) {
        console.error('Failed to save hotkey:', e);
        showToast(t('settings.error.hotkey_save_failed', { error: e.message }), 'error');
    }
}

function formatHotkey(hotkey) {
    if (!hotkey) return '';
    return hotkey.replace(/</g, '').replace(/>/g, '').replace(/\+/g, ' + ')
        .split(' + ').map(k => k.charAt(0).toUpperCase() + k.slice(1)).join(' + ');
}

// 暴露给 Python 调用
window.refreshHotkeyDisplay = async function() {
    try {
        const result = await window.api.getCurrentHotkey();
        document.getElementById('hotkey-display').value = result.formatted;
        state.settings.hotkey = result.raw;
    } catch (e) {
        console.error('Failed to refresh hotkey display:', e);
    }
};

// 语言切换处理函数
window.onLanguageChanged = async function() {
    try {
        await window.i18n.load();
        await loadLanguages();
        await loadNoAppActions();
        window.i18n.updateAllElements();
    } catch (e) {
        console.error('Failed to handle language change:', e);
    }
};

// ==================== Filters 列表 ====================

function refreshFiltersList() {
    const list = document.getElementById('filters-list');
    if (!list) return;

    list.innerHTML = '';

    if (state.filters.length === 0) {
        list.innerHTML = '<div class="list-empty">' + t('settings.conversion.no_filters') + '</div>';
        return;
    }

    state.filters.forEach((filter, index) => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.textContent = filter;
        item.onclick = () => selectFilter(index);
        // P1-13: 双击编辑功能
        item.ondblclick = () => editFilter(index);
        if (index === state.selectedFilterIndex) {
            item.classList.add('selected');
        }
        list.appendChild(item);
    });

    updateFilterButtons();
}

function selectFilter(index) {
    state.selectedFilterIndex = index;
    refreshFiltersList();
}

function updateFilterButtons() {
    const removeBtn = document.getElementById('filter-remove-btn');
    const upBtn = document.getElementById('filter-up-btn');
    const downBtn = document.getElementById('filter-down-btn');

    if (!removeBtn) return;

    const hasSelection = state.selectedFilterIndex >= 0 && state.selectedFilterIndex < state.filters.length;

    removeBtn.disabled = !hasSelection;
    upBtn.disabled = !hasSelection || state.selectedFilterIndex === 0;
    downBtn.disabled = !hasSelection || state.selectedFilterIndex === state.filters.length - 1;
}

async function addFilter() {
    try {
        const fileTypes = JSON.stringify([
            { name: 'Lua Script', pattern: '*.lua' },
            { name: 'All Files', pattern: '*' }
        ]);
        const path = await window.api.browseFile(fileTypes, '');
        if (path) {
            state.filters.push(path);
            state.selectedFilterIndex = state.filters.length - 1;
            refreshFiltersList();
        }
    } catch (e) {
        console.error('Failed to add filter:', e);
    }
}

function removeFilter() {
    if (state.selectedFilterIndex >= 0 && state.selectedFilterIndex < state.filters.length) {
        state.filters.splice(state.selectedFilterIndex, 1);
        state.selectedFilterIndex = Math.min(state.selectedFilterIndex, state.filters.length - 1);
        refreshFiltersList();
    }
}

function moveFilterUp() {
    if (state.selectedFilterIndex > 0) {
        const temp = state.filters[state.selectedFilterIndex];
        state.filters[state.selectedFilterIndex] = state.filters[state.selectedFilterIndex - 1];
        state.filters[state.selectedFilterIndex - 1] = temp;
        state.selectedFilterIndex--;
        refreshFiltersList();
    }
}

function moveFilterDown() {
    if (state.selectedFilterIndex >= 0 && state.selectedFilterIndex < state.filters.length - 1) {
        const temp = state.filters[state.selectedFilterIndex];
        state.filters[state.selectedFilterIndex] = state.filters[state.selectedFilterIndex + 1];
        state.filters[state.selectedFilterIndex + 1] = temp;
        state.selectedFilterIndex++;
        refreshFiltersList();
    }
}

/**
 * P1-13: 编辑选中的 Filter
 */
async function editFilter(index) {
    if (index < 0 || index >= state.filters.length) return;

    try {
        const currentPath = state.filters[index];
        const fileTypes = JSON.stringify([
            { name: 'Lua Script', pattern: '*.lua' },
            { name: 'All Files', pattern: '*' }
        ]);
        // 使用当前路径作为初始目录
        const path = await window.api.browseFile(fileTypes, currentPath);
        if (path) {
            state.filters[index] = path;
            refreshFiltersList();
        }
    } catch (e) {
        console.error('Failed to edit filter:', e);
    }
}

// ==================== 路径浏览 ====================

async function browseSaveDir() {
    try {
        const current = getInputValue('save-dir');
        const path = await window.api.browseDirectory(current);
        if (path) {
            setInputValue('save-dir', path);
        }
    } catch (e) {
        console.error('Failed to browse save dir:', e);
    }
}

async function restoreDefaultSaveDir() {
    try {
        const defaults = await window.api.getDefaultConfig();
        const expanded = await window.api.expandPath(defaults.save_dir);
        setInputValue('save-dir', expanded);
    } catch (e) {
        console.error('Failed to restore default save dir:', e);
    }
}

async function browsePandocPath() {
    try {
        const current = getInputValue('pandoc-path');
        const fileTypes = JSON.stringify([
            { name: 'Executable', pattern: state.platform.is_windows ? '*.exe' : '*' }
        ]);
        const path = await window.api.browseFile(fileTypes, current);
        if (path) {
            setInputValue('pandoc-path', path);
        }
    } catch (e) {
        console.error('Failed to browse pandoc path:', e);
    }
}

async function restoreDefaultPandocPath() {
    try {
        const defaults = await window.api.getDefaultConfig();
        setInputValue('pandoc-path', defaults.pandoc_path);
    } catch (e) {
        console.error('Failed to restore default pandoc path:', e);
    }
}

async function browseRefDocx() {
    try {
        const current = getInputValue('reference-docx');
        const fileTypes = JSON.stringify([
            { name: 'Word Document', pattern: '*.docx' }
        ]);
        const path = await window.api.browseFile(fileTypes, current);
        if (path) {
            setInputValue('reference-docx', path);
        }
    } catch (e) {
        console.error('Failed to browse reference docx:', e);
    }
}

function clearRefDocx() {
    setInputValue('reference-docx', '');
}

// ==================== Request Headers ====================

function toggleRequestHeadersState() {
    const enabled = getCheckbox('enable-request-headers');
    const textarea = document.getElementById('request-headers');
    if (textarea) {
        textarea.disabled = !enabled;
    }
}

function fillRequestHeadersExample() {
    setInputValue('request-headers',
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
    setCheckbox('enable-request-headers', true);
    toggleRequestHeadersState();
}

// ==================== 工具函数 ====================

function setInputValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value || '';
}

function getInputValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
}

function setCheckbox(id, checked) {
    const el = document.getElementById(id);
    if (el) el.checked = !!checked;
}

function getCheckbox(id) {
    const el = document.getElementById(id);
    return el ? el.checked : false;
}

function getSelectValue(id) {
    const el = document.getElementById(id);
    return el ? el.value : '';
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = message;
    toast.className = 'toast ' + type;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ==================== 初始化 ====================

// 等待 DOM 加载完成
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// 也监听 pywebviewready 事件
window.addEventListener('pywebviewready', () => {
    console.log('pywebview ready');
});
