/**
 * PasteMD Settings - Tab Navigation
 * 选项卡切换逻辑
 */

class TabManager {
    constructor() {
        this.tabs = [];
        this.panels = [];
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
        // 获取所有选项卡和面板，但只处理当前平台可用的
        const allTabs = document.querySelectorAll('.tab');
        const allPanels = document.querySelectorAll('.panel');

        this.tabs = Array.from(allTabs).filter(tab => this._isAvailableOnPlatform(tab));
        this.panels = Array.from(allPanels).filter(panel => this._isAvailableOnPlatform(panel));

        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabId = tab.getAttribute('data-tab');
                this.select(tabId);
            });
        });

        // 默认选中第一个可用的选项卡
        if (this.tabs.length > 0) {
            const firstTab = this.tabs[0].getAttribute('data-tab');
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

        // 更新选项卡状态
        this.tabs.forEach(tab => {
            if (tab.getAttribute('data-tab') === tabId) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
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
