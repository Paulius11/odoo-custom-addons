/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/** Popup of translation mode: the terms matching the clicked text, and a new translation. */
export class TranslationPopup extends Component {
    static template = "custom_translate.TranslationPopup";
    static components = { Dialog };
    static props = {
        text: String,
        lang: String,
        model: { type: [String, Boolean], optional: true },
        hint: { type: Object, optional: true },
        onDone: { type: Function, optional: true },
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            saving: false,
            matches: [],
            selected: {},
            value: "",
        });
        onWillStart(() => this.load());
    }

    get title() {
        return _t("Translate");
    }

    get isEnglish() {
        return this.props.lang === "en_US";
    }

    get selectedIds() {
        return this.state.matches.filter((m) => this.state.selected[m.id]).map((m) => m.id);
    }

    get canRevert() {
        return this.state.matches.some((m) => this.state.selected[m.id] && m.live);
    }

    async load() {
        const matches = this.isEnglish
            ? []
            : await this.orm.call("translation.term", "find_terms", [
                  this.props.text,
                  this.props.lang,
                  this.props.model || false,
                  this.props.hint || {},
              ]);
        let chosen = matches.filter((m) => m.suggested);
        if (!chosen.length && matches.length) {
            chosen = [matches[0]];
        }
        for (const m of chosen) {
            this.state.selected[m.id] = true;
        }
        const first = chosen[0];
        this.state.value = first ? first.pending || first.live || first.value || "" : "";
        this.state.matches = matches;
        this.state.loading = false;
    }

    toggle(match) {
        this.state.selected[match.id] = !this.state.selected[match.id];
    }

    async run(fn) {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            await fn();
            this.props.onDone?.();
            this.props.close();
        } finally {
            this.state.saving = false;
        }
    }

    async saveDraft() {
        const ids = this.selectedIds;
        const value = this.state.value.trim();
        if (!ids.length || !value) {
            this.notification.add(_t("Pick at least one term and type a translation."), {
                type: "warning",
            });
            return false;
        }
        await this.orm.call("translation.term", "save_draft", [ids, value]);
        return true;
    }

    onSaveDraft() {
        return this.run(async () => {
            if (await this.saveDraft()) {
                this.notification.add(_t("Saved as a draft. Apply makes it live."), {
                    type: "info",
                });
            }
        });
    }

    onSaveApply() {
        return this.run(async () => {
            if (await this.saveDraft()) {
                const action = await this.orm.call(
                    "translation.override",
                    "action_apply_pending",
                    [[]]
                );
                await this.action.doAction(action);
            }
        });
    }

    onRevert() {
        return this.run(async () => {
            const action = await this.orm.call("translation.term", "action_revert", [
                this.selectedIds,
            ]);
            await this.action.doAction(action);
        });
    }
}
