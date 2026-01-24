/**
 * PasteMD Settings - Extensions Manager
 * 扩展工作流管理逻辑
 */

const extensionsManager = {
    // 状态
    config: {},
    selectedApps: {
        html: -1,
        md: -1,
        latex: -1,
        file: -1
    },
    runningApps: [],
    pendingWorkflow: null,
    selectedAppForAdd: null,
    editingApp: null,
    editingWorkflow: null,

    /**
     * 初始化扩展管理器
     */
    async init() {
        try {
            // 加载配置
            await this.loadConfig();
            // 填充 UI
            this.populateUI();
        } catch (e) {
            console.error('Failed to init extensions manager:', e);
        }
    },

    /**
     * 加载扩展工作流配置
     */
    async loadConfig() {
        try {
            const response = await window.pywebview.api.extensions.get_extensible_workflows();
            const result = JSON.parse(response);
            if (result.success) {
                this.config = result.data || {};
            }
        } catch (e) {
            console.error('Failed to load extensible workflows:', e);
            this.config = {};
        }
    },

    /**
     * 填充 UI
     */
    populateUI() {
        const workflows = ['html', 'md', 'latex', 'file'];

        for (const key of workflows) {
            const cfg = this.config[key] || {};

            // 启用开关
            const enabledCheckbox = document.getElementById(`ext-${key}-enabled`);
            if (enabledCheckbox) {
                enabledCheckbox.checked = cfg.enabled || false;
            }

            // HTML 特有选项
            if (key === 'html') {
                const keepLatexCheckbox = document.getElementById('ext-html-keep-latex');
                if (keepLatexCheckbox) {
                    keepLatexCheckbox.checked = cfg.keep_formula_latex !== false;
                }
            }

            // 应用列表
            this.refreshAppList(key);
        }
    },

    /**
     * 刷新应用列表
     */
    refreshAppList(workflow) {
        const listEl = document.getElementById(`ext-${workflow}-apps`);
        if (!listEl) return;

        const cfg = this.config[workflow] || {};
        const apps = cfg.apps || [];

        listEl.innerHTML = '';

        if (apps.length === 0) {
            listEl.innerHTML = '<div class="list-empty">' + (t('settings.extensions.no_apps') || '无应用') + '</div>';
        } else {
            apps.forEach((app, index) => {
                const item = document.createElement('div');
                item.className = 'list-item';

                // 显示应用名称
                const appName = typeof app === 'object' ? app.name : app;
                item.textContent = appName;

                // 如果有窗口模式，添加提示
                if (typeof app === 'object' && app.window_patterns && app.window_patterns.length > 0) {
                    const badge = document.createElement('span');
                    badge.className = 'badge ml-sm';
                    badge.textContent = '🔍';
                    badge.title = app.window_patterns.join('\n');
                    item.appendChild(badge);
                }

                // 选中状态
                if (index === this.selectedApps[workflow]) {
                    item.classList.add('selected');
                }

                // 点击选择
                item.onclick = () => this.selectApp(workflow, index);

                // 双击编辑窗口模式
                item.ondblclick = () => this.editWindowPattern(workflow, index);

                listEl.appendChild(item);
            });
        }

        // 更新按钮状态
        this.updateButtons(workflow);
    },

    /**
     * 选择应用
     */
    selectApp(workflow, index) {
        this.selectedApps[workflow] = index;
        this.refreshAppList(workflow);
    },

    /**
     * 更新按钮状态
     */
    updateButtons(workflow) {
        const removeBtn = document.getElementById(`ext-${workflow}-remove-btn`);
        if (removeBtn) {
            const cfg = this.config[workflow] || {};
            const apps = cfg.apps || [];
            const hasSelection = this.selectedApps[workflow] >= 0 && this.selectedApps[workflow] < apps.length;
            removeBtn.disabled = !hasSelection;
        }
    },

    /**
     * 添加应用
     */
    async addApp(workflow) {
        this.pendingWorkflow = workflow;
        await this.openAppSelectModal();
    },

    /**
     * 移除应用
     */
    removeApp(workflow) {
        const cfg = this.config[workflow] || {};
        const apps = cfg.apps || [];
        const index = this.selectedApps[workflow];

        if (index >= 0 && index < apps.length) {
            apps.splice(index, 1);
            this.selectedApps[workflow] = Math.min(index, apps.length - 1);
            this.refreshAppList(workflow);
            markAsDirty();
        }
    },

    /**
     * 打开应用选择模态框
     */
    async openAppSelectModal() {
        const modal = document.getElementById('app-select-modal');
        const loadingEl = document.getElementById('app-select-loading');
        const listEl = document.getElementById('app-select-list');
        const emptyEl = document.getElementById('app-select-empty');
        const confirmBtn = document.getElementById('app-select-confirm-btn');

        if (!modal) return;

        // 显示模态框
        modal.classList.remove('hidden');

        // 显示加载状态
        loadingEl.classList.remove('hidden');
        listEl.classList.add('hidden');
        emptyEl.classList.add('hidden');
        confirmBtn.disabled = true;
        this.selectedAppForAdd = null;

        try {
            // 获取运行中的应用
            const response = await window.pywebview.api.extensions.get_running_apps();
            const result = JSON.parse(response);

            loadingEl.classList.add('hidden');

            if (result.success && result.data && result.data.length > 0) {
                this.runningApps = result.data;
                this.renderAppSelectList();
                listEl.classList.remove('hidden');
            } else {
                emptyEl.classList.remove('hidden');
            }
        } catch (e) {
            console.error('Failed to get running apps:', e);
            loadingEl.classList.add('hidden');
            emptyEl.classList.remove('hidden');
        }
    },

    /**
     * 渲染应用选择列表
     */
    renderAppSelectList() {
        const listEl = document.getElementById('app-select-list');
        if (!listEl) return;

        listEl.innerHTML = '';

        this.runningApps.forEach((app, index) => {
            const item = document.createElement('div');
            item.className = 'app-select-item';
            item.innerHTML = `
                <span class="app-name">${app.name}</span>
                <span class="app-id text-muted text-sm">${app.id}</span>
            `;
            item.onclick = () => this.selectAppForAdd(index);
            listEl.appendChild(item);
        });
    },

    /**
     * 选择要添加的应用
     */
    selectAppForAdd(index) {
        const listEl = document.getElementById('app-select-list');
        const confirmBtn = document.getElementById('app-select-confirm-btn');

        // 更新选中状态
        const items = listEl.querySelectorAll('.app-select-item');
        items.forEach((item, i) => {
            if (i === index) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });

        this.selectedAppForAdd = this.runningApps[index];
        confirmBtn.disabled = false;
    },

    /**
     * 确认添加应用
     */
    async confirmAppSelection() {
        if (!this.selectedAppForAdd || !this.pendingWorkflow) {
            this.closeAppSelectModal();
            return;
        }

        const app = this.selectedAppForAdd;
        const workflow = this.pendingWorkflow;

        try {
            // 检查是否为保留应用
            const reservedResponse = await window.pywebview.api.extensions.is_reserved_app(app.id);
            const reservedResult = JSON.parse(reservedResponse);
            if (reservedResult.success && reservedResult.data.is_reserved) {
                showToast(t('settings.extensions.reserved_app_error', { app: app.name }), 'error');
                return;
            }

            // 检查是否已在当前工作流中
            const cfg = this.config[workflow] || {};
            const apps = cfg.apps || [];
            const exists = apps.some(a => {
                const existingId = typeof a === 'object' ? a.id : a;
                return existingId && existingId.toLowerCase() === app.id.toLowerCase();
            });

            if (exists) {
                showToast(t('settings.extensions.app_exists', { app: app.name }), 'warning');
                return;
            }

            // 检查是否在其他工作流中
            const conflictResponse = await window.pywebview.api.extensions.check_app_conflict(workflow, app.id);
            const conflictResult = JSON.parse(conflictResponse);

            if (conflictResult.success && conflictResult.data.has_conflict) {
                const conflictWorkflow = conflictResult.data.conflict_workflow;
                // 可以继续添加（用于不同窗口模式）
                if (!confirm(t('settings.extensions.app_conflict_error', {
                    app: app.name,
                    workflow: conflictWorkflow
                }))) {
                    return;
                }
            }

            // 添加应用
            if (!this.config[workflow]) {
                this.config[workflow] = { enabled: false, apps: [] };
            }
            if (!this.config[workflow].apps) {
                this.config[workflow].apps = [];
            }

            this.config[workflow].apps.push({
                name: app.name,
                id: app.id,
                window_patterns: []
            });

            this.selectedApps[workflow] = this.config[workflow].apps.length - 1;
            this.refreshAppList(workflow);
            markAsDirty();

        } catch (e) {
            console.error('Failed to add app:', e);
            showToast(t('settings.error.save_failed', { error: e.message }), 'error');
        }

        this.closeAppSelectModal();
    },

    /**
     * 关闭应用选择模态框
     */
    closeAppSelectModal() {
        const modal = document.getElementById('app-select-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
        this.pendingWorkflow = null;
        this.selectedAppForAdd = null;
    },

    /**
     * 编辑窗口模式
     */
    editWindowPattern(workflow, index) {
        const cfg = this.config[workflow] || {};
        const apps = cfg.apps || [];
        const app = apps[index];

        if (!app) return;

        this.editingWorkflow = workflow;
        this.editingApp = index;

        const modal = document.getElementById('window-pattern-modal');
        const appNameEl = document.getElementById('window-pattern-app-name');
        const inputEl = document.getElementById('window-pattern-input');

        if (!modal) return;

        // 填充数据
        const appName = typeof app === 'object' ? app.name : app;
        appNameEl.textContent = appName;

        const patterns = typeof app === 'object' ? (app.window_patterns || []) : [];
        inputEl.value = patterns.join('\n');

        modal.classList.remove('hidden');
    },

    /**
     * 保存窗口模式
     */
    saveWindowPattern() {
        const inputEl = document.getElementById('window-pattern-input');
        if (!inputEl || this.editingWorkflow === null || this.editingApp === null) {
            this.closeWindowPatternModal();
            return;
        }

        const patterns = inputEl.value.split('\n').filter(p => p.trim());

        const cfg = this.config[this.editingWorkflow] || {};
        const apps = cfg.apps || [];
        const app = apps[this.editingApp];

        if (app && typeof app === 'object') {
            app.window_patterns = patterns;
        }

        this.refreshAppList(this.editingWorkflow);
        markAsDirty();
        this.closeWindowPatternModal();
    },

    /**
     * 关闭窗口模式编辑模态框
     */
    closeWindowPatternModal() {
        const modal = document.getElementById('window-pattern-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
        this.editingWorkflow = null;
        this.editingApp = null;
    },

    /**
     * 收集扩展工作流配置
     */
    collectConfig() {
        const workflows = ['html', 'md', 'latex', 'file'];

        for (const key of workflows) {
            if (!this.config[key]) {
                this.config[key] = { enabled: false, apps: [] };
            }

            // 启用状态
            const enabledCheckbox = document.getElementById(`ext-${key}-enabled`);
            if (enabledCheckbox) {
                this.config[key].enabled = enabledCheckbox.checked;
            }

            // HTML 特有选项
            if (key === 'html') {
                const keepLatexCheckbox = document.getElementById('ext-html-keep-latex');
                if (keepLatexCheckbox) {
                    this.config[key].keep_formula_latex = keepLatexCheckbox.checked;
                }
            }
        }

        return this.config;
    },

    /**
     * 保存扩展工作流配置
     */
    async save() {
        try {
            const config = this.collectConfig();
            const response = await window.pywebview.api.extensions.save_extensible_workflows(JSON.stringify(config));
            const result = JSON.parse(response);

            if (!result.success) {
                // 检查是否为冲突警告
                if (result.error && result.error.code === 'CONFLICT_WARNING') {
                    showToast(result.error.message, 'warning', 5000);
                    return false;
                }
                throw new Error(result.error?.message || 'Save failed');
            }

            return true;
        } catch (e) {
            console.error('Failed to save extensible workflows:', e);
            throw e;
        }
    }
};

// 暴露到全局
window.extensionsManager = extensionsManager;
