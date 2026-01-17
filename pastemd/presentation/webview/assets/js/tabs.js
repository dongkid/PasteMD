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
     * 初始化选项卡
     */
    init() {
        this.tabs = document.querySelectorAll('.tab');
        this.panels = document.querySelectorAll('.panel');

        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabId = tab.getAttribute('data-tab');
                this.select(tabId);
            });
        });

        // 默认选中第一个
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
