/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

import { Component, useState, onWillStart } from "@odoo/owl";

export class LanguageSwitcher extends Component {
    static template = "language_switcher.LanguageSwitcher";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.languageService = useService("language");
        this.state = useState({
            languages: [],
            currentLang: null,
            loading: false
        });

        onWillStart(async () => {
            await this.loadLanguages();
        });
    }

    async loadLanguages() {
        this.state.loading = true;
        try {
            this.state.languages = await this.languageService.getLanguages();
            this.state.currentLang = this.languageService.getCurrentLanguage();
        } catch (error) {
            console.error("Failed to load languages:", error);
        } finally {
            this.state.loading = false;
        }
    }

    getCurrentLanguageName() {
        if (!this.state.languages.length || !this.state.currentLang) {
            return "";
        }
        const currentLang = this.state.languages.find(lang => lang.code === this.state.currentLang);
        return currentLang ? currentLang.name : this.state.currentLang;
    }

    async switchLanguage(langCode) {
        if (langCode === this.state.currentLang) {
            return;
        }
        
        await this.languageService.switchLanguage(langCode);
    }
}

export const languageSwitcherItem = {
    Component: LanguageSwitcher,
};

registry.category("systray").add("languageSwitcher", languageSwitcherItem, { sequence: 15 });