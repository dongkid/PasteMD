/**
 * PasteMD Settings - Hotkey Recording
 * 热键录制逻辑
 */

class HotkeyRecorder {
    constructor() {
        this.isRecording = false;
        this.pressedKeys = new Set();
        this.allPressedKeys = new Set();
        this.releasedKeys = new Set();
        this.platform = 'windows';
        this.onUpdate = null;
        this.onFinish = null;
    }

    /**
     * 初始化
     */
    async init() {
        try {
            const platformInfo = await window.api.getHotkeyPlatform();
            this.platform = platformInfo.platform;
        } catch (e) {
            console.error('Failed to get platform:', e);
        }
    }

    /**
     * 开始录制
     * @param {function} onUpdate - 更新回调
     * @param {function} onFinish - 完成回调
     */
    async start(onUpdate, onFinish) {
        if (this.isRecording) return;

        this.isRecording = true;
        this.pressedKeys.clear();
        this.allPressedKeys.clear();
        this.releasedKeys.clear();
        this.onUpdate = onUpdate;
        this.onFinish = onFinish;

        if (this.platform === 'macos') {
            // macOS: 使用 JavaScript 键盘事件
            this._bindKeyEvents();
        } else {
            // Windows: 使用 Python pynput
            try {
                await window.api.startRecordingWindows();
            } catch (e) {
                console.error('Failed to start Windows recording:', e);
                this.stop();
            }
        }
    }

    /**
     * 停止录制
     */
    async stop() {
        if (!this.isRecording) return;

        this.isRecording = false;

        if (this.platform === 'macos') {
            this._unbindKeyEvents();
        } else {
            try {
                await window.api.stopRecordingWindows();
            } catch (e) {
                console.error('Failed to stop Windows recording:', e);
            }
        }

        this.onUpdate = null;
        this.onFinish = null;
    }

    /**
     * 绑定键盘事件 (macOS)
     */
    _bindKeyEvents() {
        this._keyDownHandler = (e) => this._onKeyDown(e);
        this._keyUpHandler = (e) => this._onKeyUp(e);

        document.addEventListener('keydown', this._keyDownHandler);
        document.addEventListener('keyup', this._keyUpHandler);
    }

    /**
     * 解绑键盘事件
     */
    _unbindKeyEvents() {
        if (this._keyDownHandler) {
            document.removeEventListener('keydown', this._keyDownHandler);
            this._keyDownHandler = null;
        }
        if (this._keyUpHandler) {
            document.removeEventListener('keyup', this._keyUpHandler);
            this._keyUpHandler = null;
        }
    }

    /**
     * 键盘按下事件
     */
    _onKeyDown(e) {
        if (!this.isRecording) return;

        e.preventDefault();
        e.stopPropagation();

        const keyName = this._getKeyName(e);
        if (!keyName) return;

        if (this.pressedKeys.has(keyName)) return;

        this.pressedKeys.add(keyName);
        this.allPressedKeys.add(keyName);
        this._notifyUpdate();
    }

    /**
     * 键盘释放事件
     */
    _onKeyUp(e) {
        if (!this.isRecording) return;

        e.preventDefault();
        e.stopPropagation();

        const keyName = this._getKeyName(e);
        if (!keyName) return;

        this.releasedKeys.add(keyName);
        this.pressedKeys.delete(keyName);
        this._notifyUpdate();

        // 检查是否所有键都已释放
        if (this.allPressedKeys.size > 0 &&
            this.allPressedKeys.size === this.releasedKeys.size) {
            this._finishRecording();
        }
    }

    /**
     * 获取键名
     */
    _getKeyName(e) {
        const key = e.key.toLowerCase();

        // 修饰键
        if (e.ctrlKey && (key === 'control' || key === 'ctrl')) return 'ctrl';
        if (e.shiftKey && key === 'shift') return 'shift';
        if (e.altKey && (key === 'alt' || key === 'option')) return 'alt';
        if (e.metaKey && (key === 'meta' || key === 'command' || key === 'cmd')) return 'cmd';

        // 特殊键
        if (key === 'control' || key === 'ctrl') return 'ctrl';
        if (key === 'shift') return 'shift';
        if (key === 'alt' || key === 'option') return 'alt';
        if (key === 'meta' || key === 'command' || key === 'cmd') return 'cmd';
        if (key === 'enter' || key === 'return') return 'enter';
        if (key === 'escape' || key === 'esc') return 'esc';
        if (key === ' ') return 'space';
        if (key === 'tab') return 'tab';
        if (key === 'backspace') return 'backspace';
        if (key === 'delete') return 'delete';

        // 字母/数字键
        if (key.length === 1) return key;

        // 其他键
        return key;
    }

    /**
     * 通知更新
     */
    _notifyUpdate() {
        if (!this.onUpdate || !this.allPressedKeys.size) return;

        const displayText = this._formatKeys(this.allPressedKeys);
        this.onUpdate(displayText);
    }

    /**
     * 完成录制
     */
    async _finishRecording() {
        const keys = Array.from(this.allPressedKeys);
        this.stop();

        if (keys.length === 0) {
            if (this.onFinish) {
                this.onFinish(null, 'No key detected');
            }
            return;
        }

        try {
            const result = await window.api.validateHotkey(keys);
            if (this.onFinish) {
                this.onFinish(result.hotkey, null);
            }
        } catch (e) {
            if (this.onFinish) {
                this.onFinish(null, e.message);
            }
        }
    }

    /**
     * 格式化按键显示
     */
    _formatKeys(keys) {
        const modifierOrder = ['ctrl', 'shift', 'alt', 'cmd'];
        const modifiers = modifierOrder.filter(m => keys.has(m));
        const normalKeys = Array.from(keys).filter(k => !modifierOrder.includes(k)).sort();

        const allKeys = [...modifiers, ...normalKeys];
        return allKeys.map(k => k.charAt(0).toUpperCase() + k.slice(1)).join(' + ');
    }
}

// 全局热键录制器
window.hotkeyRecorder = new HotkeyRecorder();

// Python 回调 (Windows 平台)
window.onHotkeyUpdate = (displayText) => {
    if (window.hotkeyRecorder.onUpdate) {
        window.hotkeyRecorder.onUpdate(displayText);
    }
};

window.onHotkeyFinish = (result) => {
    window.hotkeyRecorder.isRecording = false;
    if (window.hotkeyRecorder.onFinish) {
        window.hotkeyRecorder.onFinish(result.hotkey, result.error);
    }
};
