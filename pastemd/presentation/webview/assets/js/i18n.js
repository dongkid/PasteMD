/**
 * PasteMD Settings - Internationalization
 * 前端国际化支持
 */

class I18n {
    constructor() {
        this.translations = {};
        this.loaded = false;
    }

    /**
     * 加载翻译
     */
    async load() {
        try {
            this.translations = await window.api.getTranslations();
            this.loaded = true;
            this.updateAllElements();
        } catch (e) {
            console.error('Failed to load translations:', e);
        }
    }

    /**
     * 获取翻译文本
     * @param {string} key - 翻译键
     * @param {object} params - 替换参数
     * @returns {string} 翻译后的文本
     */
    t(key, params = {}) {
        let text = this.translations[key] || key;

        // 替换参数 {name} -> value
        for (const [name, value] of Object.entries(params)) {
            text = text.replace(new RegExp(`\\{${name}\\}`, 'g'), value);
        }

        return text;
    }

    /**
     * 更新所有带 data-i18n 属性的元素
     */
    updateAllElements() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                el.textContent = this.t(key);
            }
        });

        // 更新 placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) {
                el.placeholder = this.t(key);
            }
        });

        // 更新 title
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                el.title = this.t(key);
            }
        });
    }
}

// 全局 i18n 实例
window.i18n = new I18n();

// 快捷函数
window.t = (key, params) => window.i18n.t(key, params);
