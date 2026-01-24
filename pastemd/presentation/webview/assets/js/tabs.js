/**
 * PasteMD Settings - Tab Navigation
 * 选项卡切换逻辑 (Fluent Design 侧边栏版本)
 */

class TabManager {
    constructor() {
        this.navItems = [];
        this.panels = [];
        this.pageTitle = null;
        this.currentTab = 'general';
    }

    /**
     * 检查元素是否在当前平台可用
     * @param {Element} element - 要检查的元素
     * @returns {boolean} - 是否可用
     */
    _isAvailableOnPlatform(element) {
        const platform = window.state?.platform || {};

        // macOS 专属元素：仅在 macOS 可用
        if (element.classList.contains('macos-only')) {
            return platform.is_macos === true;
        }

        // Windows 专属元素：仅在 Windows 可用
        if (element.classList.contains('windows-only')) {
            return platform.is_windows === true;
        }

        // 无平台限制
        return true;
    }

    /**
     * 初始化选项卡
     */
    init() {
        // 获取所有导航项和面板，但只处理当前平台可用的
        const allNavItems = document.querySelectorAll('.nav-item');
        const allPanels = document.querySelectorAll('.panel');
        this.pageTitle = document.querySelector('.page-title');

        this.navItems = Array.from(allNavItems).filter(item => this._isAvailableOnPlatform(item));
        this.panels = Array.from(allPanels).filter(panel => this._isAvailableOnPlatform(panel));

        // 为兼容性也检查旧的 .tab 选择器
        const oldTabs = document.querySelectorAll('.tab');
        if (oldTabs.length > 0 && this.navItems.length === 0) {
            this.navItems = Array.from(oldTabs).filter(tab => this._isAvailableOnPlatform(tab));
        }

        this.navItems.forEach(item => {
            item.addEventListener('click', () => {
                const tabId = item.getAttribute('data-tab');
                this.select(tabId);
            });
        });

        // 默认选中第一个可用的选项卡
        if (this.navItems.length > 0) {
            const firstTab = this.navItems[0].getAttribute('data-tab');
            this.select(firstTab);
        }
    }

    /**
     * 选择选项卡
     * @param {string} tabId - 选项卡 ID
     */
    select(tabId) {
        const previousTab = this.currentTab;
        this.currentTab = tabId;

        // 更新导航项状态
        this.navItems.forEach(item => {
            if (item.getAttribute('data-tab') === tabId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        // 更新面板显示
        this.panels.forEach(panel => {
            if (panel.id === `panel-${tabId}`) {
                panel.classList.add('active');
            } else {
                panel.classList.remove('active');
            }
        });

        // 更新页面标题
        const activeItem = this.navItems.find(item => item.getAttribute('data-tab') === tabId);
        if (this.pageTitle && activeItem) {
            const labelEl = activeItem.querySelector('.nav-label');
            if (labelEl) {
                this.pageTitle.textContent = labelEl.textContent;
                const i18nKey = labelEl.getAttribute('data-i18n');
                if (i18nKey) {
                    this.pageTitle.setAttribute('data-i18n', i18nKey);
                }
            }
        }

        // P1-9: 权限轮询优化 - 仅在 permissions 选项卡可见时轮询
        if (window.permissionsManager) {
            if (tabId === 'permissions') {
                window.permissionsManager.startAutoRefresh();
            } else if (previousTab === 'permissions') {
                window.permissionsManager.stopAutoRefresh();
            }
        }
    }

    /**
     * 获取当前选项卡
     */
    getCurrent() {
        return this.currentTab;
    }
}

// 全局选项卡管理器
window.tabManager = new TabManager();

// 暴露给 Python 调用的函数
window.selectTab = (tabId) => {
    window.tabManager.select(tabId);
};
