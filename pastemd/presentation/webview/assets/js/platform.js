/**
 * PasteMD Settings - Platform Effects Manager
 * 管理平台特定的视觉效果（Windows 11 Mica / macOS Vibrancy）
 */

window.platformEffects = {
    // 状态标志
    micaEnabled: false,
    vibrancyEnabled: false,
    initialized: false,

    /**
     * 初始化平台效果
     * @param {Object} platform - 平台信息对象 { is_windows, is_macos }
     */
    init: function(platform) {
        if (this.initialized) {
            return;
        }

        if (platform.is_windows) {
            this.initWindowsEffects();
        } else if (platform.is_macos) {
            this.initMacOSEffects();
        }

        this.initialized = true;
        console.log('Platform effects initialized:', {
            mica: this.micaEnabled,
            vibrancy: this.vibrancyEnabled
        });
    },

    /**
     * Windows 效果初始化
     * Mica class 由 Python 端在窗口加载后设置
     */
    initWindowsEffects: function() {
        const self = this;

        // 检查 Mica class（由 Python 端设置）
        const checkMica = () => {
            if (document.documentElement.classList.contains('mica-enabled')) {
                if (!self.micaEnabled) {
                    self.micaEnabled = true;
                    self.applyTransparentBackground();
                    console.log('Windows Mica effect detected and enabled');
                }
            }
        };

        // 立即检查一次
        checkMica();

        // 监听 class 变化（Python 端会在窗口加载后添加 mica-enabled class）
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'class') {
                    checkMica();
                }
            });
        });

        observer.observe(document.documentElement, { attributes: true });
    },

    /**
     * macOS 效果初始化
     * pywebview 的 vibrancy 参数会自动处理系统层面的效果
     */
    initMacOSEffects: function() {
        this.vibrancyEnabled = true;
        document.body.classList.add('vibrancy-enabled');
        this.applyTransparentBackground();
        console.log('macOS vibrancy effect enabled');
    },

    /**
     * 应用透明背景
     */
    applyTransparentBackground: function() {
        document.body.style.backgroundColor = 'transparent';

        const app = document.querySelector('.app');
        if (app) {
            app.style.background = 'transparent';
        }
    },

    /**
     * 主题变更时更新效果
     * @param {string} theme - 主题名称 ('auto', 'light', 'dark')
     */
    onThemeChange: function(theme) {
        // 通知 Python 端更新 Mica 颜色模式（仅 Windows）
        if (this.micaEnabled && window.pywebview && window.pywebview.api) {
            const isDark = theme === 'dark' ||
                (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);

            // 调用 API 更新 Mica 主题（如果存在）
            if (window.api && typeof window.api.updateMicaTheme === 'function') {
                window.api.updateMicaTheme(isDark ? 'dark' : 'light')
                    .then(() => console.log('Mica theme updated:', isDark ? 'dark' : 'light'))
                    .catch((e) => console.log('Mica theme update not available:', e.message));
            }
        }
    },

    /**
     * 检查是否启用了任何视觉效果
     * @returns {boolean}
     */
    hasVisualEffects: function() {
        return this.micaEnabled || this.vibrancyEnabled;
    }
};
