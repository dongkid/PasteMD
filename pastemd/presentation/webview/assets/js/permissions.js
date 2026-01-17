/**
 * PasteMD Settings - Permissions (macOS)
 * macOS 权限检测逻辑
 */

class PermissionsManager {
    constructor() {
        this.permissions = {};
        this.refreshInterval = null;
        this.info = {};
    }

    /**
     * 初始化
     */
    async init() {
        try {
            // 检查是否是 macOS
            const isMac = await window.api.isMacOS();
            if (!isMac) {
                // 非 macOS，隐藏权限选项卡
                const tab = document.querySelector('.tab[data-tab="permissions"]');
                if (tab) tab.style.display = 'none';
                return;
            }

            // 加载权限信息
            this.info = await window.api.getPermissionInfo();

            // 初始刷新
            await this.refresh();

            // 设置定时刷新
            this.startAutoRefresh();

        } catch (e) {
            console.error('Failed to init permissions:', e);
        }
    }

    /**
     * 刷新权限状态
     */
    async refresh() {
        try {
            this.permissions = await window.api.getAllPermissions();
            this.updateUI();
            this.updateLastChecked();
        } catch (e) {
            console.error('Failed to refresh permissions:', e);
        }
    }

    /**
     * 更新 UI
     */
    updateUI() {
        const container = document.getElementById('permissions-list');
        if (!container) return;

        const permTypes = ['accessibility', 'screen_recording', 'input_monitoring', 'automation'];

        permTypes.forEach(type => {
            const perm = this.permissions[type];
            if (!perm) return;

            const statusEl = document.querySelector(`[data-permission="${type}"] .permission-status`);
            const dotEl = document.querySelector(`[data-permission="${type}"] .status-dot`);
            const requestBtn = document.querySelector(`[data-permission="${type}"] .btn-request`);

            if (statusEl) {
                statusEl.textContent = perm.status_text;
                statusEl.style.color = perm.status_color;
            }

            if (dotEl) {
                dotEl.className = 'status-dot';
                if (perm.status === true) {
                    dotEl.classList.add('granted');
                } else if (perm.status === false) {
                    dotEl.classList.add('missing');
                } else {
                    dotEl.classList.add('unknown');
                }
            }

            if (requestBtn) {
                if (perm.status === false) {
                    requestBtn.style.display = 'inline-flex';
                } else {
                    requestBtn.style.display = 'none';
                }
            }
        });
    }

    /**
     * 更新最后检查时间
     */
    updateLastChecked() {
        const el = document.getElementById('last-checked');
        if (el) {
            const now = new Date();
            const time = now.toLocaleTimeString();
            el.textContent = this.info.last_checked?.replace('--:--:--', time) ||
                `Last checked: ${time}`;
        }
    }

    /**
     * 请求权限
     */
    async requestPermission(type) {
        try {
            await window.api.requestPermission(type);
            // 延迟刷新
            setTimeout(() => this.refresh(), 1200);
        } catch (e) {
            console.error(`Failed to request permission ${type}:`, e);
        }
    }

    /**
     * 打开系统设置
     */
    async openSettings(type) {
        try {
            await window.api.openSystemSettings(type);
        } catch (e) {
            console.error(`Failed to open settings for ${type}:`, e);
        }
    }

    /**
     * 开始自动刷新
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        this.refreshInterval = setInterval(() => this.refresh(), 2000);
    }

    /**
     * 停止自动刷新
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
}

// 全局权限管理器
window.permissionsManager = new PermissionsManager();
