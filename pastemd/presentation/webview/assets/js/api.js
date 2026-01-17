/**
 * PasteMD Settings - Python API Wrapper
 * 封装 Python API 调用，提供类型安全的接口
 */

class ApiWrapper {
    constructor() {
        this._ready = false;
        this._pendingCalls = [];
        this._queuePollingInterval = null;
    }

    /**
     * 等待 API 就绪
     */
    async waitReady() {
        if (this._ready) return;

        return new Promise((resolve) => {
            const check = () => {
                if (window.pywebview && window.pywebview.api) {
                    this._ready = true;
                    // 执行等待中的调用
                    this._pendingCalls.forEach(fn => fn());
                    this._pendingCalls = [];
                    // 启动 UI 队列轮询
                    this._startQueuePolling();
                    resolve();
                } else {
                    setTimeout(check, 50);
                }
            };
            check();
        });
    }

    /**
     * 启动 UI 队列轮询
     * 定时调用 Python 端的 process_ui_queue 方法，
     * 确保跨线程的 GUI 操作在正确的线程执行
     */
    _startQueuePolling() {
        if (this._queuePollingInterval) return;

        this._queuePollingInterval = setInterval(async () => {
            try {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.process_ui_queue) {
                    await window.pywebview.api.process_ui_queue();
                }
            } catch (e) {
                // 静默处理错误，避免控制台刷屏
            }
        }, 100); // 100ms 轮询间隔
    }

    /**
     * 停止 UI 队列轮询
     */
    _stopQueuePolling() {
        if (this._queuePollingInterval) {
            clearInterval(this._queuePollingInterval);
            this._queuePollingInterval = null;
        }
    }

    /**
     * 调用 Python API
     * @param {string} method - 方法名 (如 "get_settings" 或 "hotkey.get_current_hotkey")
     * @param  {...any} args - 参数
     * @returns {Promise<any>} 解析后的响应数据
     */
    async _call(method, ...args) {
        await this.waitReady();

        try {
            const parts = method.split('.');
            let fn = window.pywebview.api;

            for (const part of parts) {
                fn = fn[part];
                if (!fn) {
                    throw new Error(`API method not found: ${method}`);
                }
            }

            const result = await fn.apply(null, args);
            const parsed = JSON.parse(result);

            if (parsed.success) {
                return parsed.data;
            } else {
                throw new Error(parsed.error?.message || 'Unknown error');
            }
        } catch (e) {
            console.error(`API call failed: ${method}`, e);
            throw e;
        }
    }

    // ==================== Settings API ====================

    async getSettings() {
        return await this._call('get_settings');
    }

    async saveSettings(settings) {
        return await this._call('save_settings', JSON.stringify(settings));
    }

    async getLanguages() {
        return await this._call('get_languages');
    }

    async getNoAppActions() {
        return await this._call('get_no_app_actions');
    }

    async browseDirectory(initialDir = '') {
        return await this._call('browse_directory', initialDir);
    }

    async browseFile(fileTypes = '', initialDir = '') {
        return await this._call('browse_file', fileTypes, initialDir);
    }

    async getDefaultConfig() {
        return await this._call('get_default_config');
    }

    async expandPath(path) {
        return await this._call('expand_path', path);
    }

    async getTranslations() {
        return await this._call('get_translations');
    }

    async getPlatform() {
        return await this._call('get_platform');
    }

    async closeWindow() {
        return await this._call('close_window');
    }

    async minimizeWindow() {
        return await this._call('minimize_window');
    }

    // ==================== Hotkey API ====================

    async getCurrentHotkey() {
        return await this._call('hotkey.get_current_hotkey');
    }

    async startRecordingWindows() {
        return await this._call('hotkey.start_recording_windows');
    }

    async stopRecordingWindows() {
        return await this._call('hotkey.stop_recording_windows');
    }

    async validateHotkey(keys) {
        return await this._call('hotkey.validate_hotkey', JSON.stringify(keys));
    }

    async checkHotkeyConflict(hotkeyStr) {
        return await this._call('hotkey.check_hotkey_conflict', hotkeyStr);
    }

    async saveHotkey(hotkeyStr) {
        return await this._call('hotkey.save_hotkey', hotkeyStr);
    }

    async getHotkeyPlatform() {
        return await this._call('hotkey.get_platform');
    }

    // ==================== Permissions API ====================

    async isMacOS() {
        return await this._call('permissions.is_macos');
    }

    async getAllPermissions() {
        return await this._call('permissions.get_all_permissions');
    }

    async checkPermission(permissionType) {
        return await this._call('permissions.check_permission', permissionType);
    }

    async requestPermission(permissionType) {
        return await this._call('permissions.request_permission', permissionType);
    }

    async openSystemSettings(permissionType) {
        return await this._call('permissions.open_system_settings', permissionType);
    }

    async getPermissionInfo() {
        return await this._call('permissions.get_permission_info');
    }
}

// 全局 API 实例
window.api = new ApiWrapper();
