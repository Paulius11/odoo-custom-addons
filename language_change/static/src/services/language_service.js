/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

/**
 * Service to handle language switching functionality
 */
export const languageService = {
    dependencies: ["notification"],

    start(env, { notification }) {
        let languages = null;

        return {
            /**
             * Get all active languages in the system
             * @returns {Promise<Array>} languages
             */
            async getLanguages() {
                if (languages) {
                    return languages;
                }
                
                try {
                    languages = await rpc("/web/dataset/call_kw/res.lang/search_read", {
                        model: "res.lang",
                        method: "search_read",
                        args: [[["active", "=", true]]],
                        kwargs: { fields: ["name", "code"] },
                    });
                    return languages;
                } catch (error) {
                    console.error("Failed to fetch languages:", error);
                    notification.add(_t("Failed to load languages."), {
                        type: "danger",
                    });
                    return [];
                }
            },

            /**
             * Switch user language
             * @param {String} langCode 
             * @returns {Promise<Boolean>} success
             */
            async switchLanguage(langCode) {
                try {
                    const result = await rpc("/language_switcher/switch_language", {
                        lang_code: langCode,
                    });
                    
                    if (result.success) {
                        // Reload the page to apply the language change
                        browser.location.reload();
                        return true;
                    } else {
                        notification.add(result.error || _t("Failed to switch language."), {
                            type: "danger",
                        });
                        return false;
                    }
                } catch (error) {
                    console.error("Failed to switch language:", error);
                    notification.add(_t("Failed to switch language."), {
                        type: "danger",
                    });
                    return false;
                }
            },

            /**
             * Get current language code
             * @returns {String} langCode
             */
            getCurrentLanguage() {
                // user.lang is a browser locale ("en-US"); res.lang codes look like "en_US"
                return user.context.lang || 'en_US';
            }
        };
    },
};

registry.category("services").add("language", languageService);