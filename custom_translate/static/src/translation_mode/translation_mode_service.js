/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Shared state of translation mode: on/off and the number of drafts waiting
 * for Apply. Components read `state`; the overlay does the DOM work.
 */
export const translationModeService = {
    dependencies: ["orm", "user"],

    async start(env, { orm, user }) {
        const isTranslator = await user.hasGroup("custom_translate.group_translator");
        // stays on across the page reload that Apply triggers
        const KEY = "custom_translate.enabled";
        let enabled = false;
        try {
            enabled = isTranslator && sessionStorage.getItem(KEY) === "1";
        } catch {
            // storage blocked: start off
        }
        const state = reactive({ enabled, pending: 0 });

        async function refreshPending() {
            if (isTranslator) {
                state.pending = await orm.call("translation.term", "get_pending_count", []);
            }
        }

        if (enabled) {
            refreshPending();
        }
        return {
            isTranslator,
            state,
            lang: user.lang,
            refreshPending,
            toggle() {
                state.enabled = !state.enabled;
                try {
                    sessionStorage.setItem(KEY, state.enabled ? "1" : "0");
                } catch {
                    // storage blocked: not remembered
                }
                if (state.enabled) {
                    refreshPending();
                }
            },
        };
    },
};

registry.category("services").add("translationMode", translationModeService);
