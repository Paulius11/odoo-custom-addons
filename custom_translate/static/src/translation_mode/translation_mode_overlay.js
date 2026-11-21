/** @odoo-module **/

import { Component, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { TranslationPopup } from "./translation_popup";

// stays clickable while translation mode is on: our own UI, and the controls of an
// error dialog and of notifications (else Close opens another popup); the error
// text itself can still be clicked to translate it
const OWN_UI = [
    ".o_translation_popup_dialog",
    ".o_translation_mode_bar",
    ".o_translation_mode_systray",
    ".o_error_dialog .modal-header",
    ".o_error_dialog .modal-footer",
    ".o_error_dialog button",
    ".o_notification_manager",
].join(", ");

/** The text a click on `el` means: its own text, else a short full text, else a placeholder. */
export function textOf(el) {
    for (let node = el, depth = 0; node && depth < 4; node = node.parentElement, depth++) {
        if (node.placeholder) {
            return node.placeholder.trim();
        }
        let own = "";
        for (const child of node.childNodes) {
            if (child.nodeType === Node.TEXT_NODE) {
                own += child.textContent;
            }
        }
        own = own.replace(/\s+/g, " ").trim();
        if (own) {
            return own;
        }
        const full = (node.textContent || "").replace(/\s+/g, " ").trim();
        if (full && full.length <= 200) {
            return full;
        }
    }
    return "";
}

/** Where the click landed, so the server can pre-tick the right matches. */
export function hintOf(el) {
    const menu = el.closest("[data-section]");
    if (menu && el.closest(".o_main_navbar")) {
        return { menu_id: parseInt(menu.dataset.section, 10) };
    }
    if (el.closest(".o_main_navbar")) {
        return { area: "menu" };
    }
    if (el.closest(".o_form_label, .o_list_table thead, label")) {
        return { area: "label" };
    }
    return {};
}

export class TranslationModeOverlay extends Component {
    static template = "custom_translate.TranslationModeOverlay";
    static props = {};

    setup() {
        this.translationMode = useService("translationMode");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState(this.translationMode.state);
        this.hovered = null;
        this.onClick = this.onClick.bind(this);
        this.onOver = this.onOver.bind(this);

        useEffect(
            (enabled) => {
                if (!enabled) {
                    return;
                }
                document.body.classList.add("o_translation_mode_active");
                document.addEventListener("click", this.onClick, true);
                document.addEventListener("mouseover", this.onOver, true);
                return () => {
                    document.body.classList.remove("o_translation_mode_active");
                    document.removeEventListener("click", this.onClick, true);
                    document.removeEventListener("mouseover", this.onOver, true);
                    this.setHovered(null);
                };
            },
            () => [this.state.enabled]
        );
    }

    setHovered(el) {
        this.hovered?.classList.remove("o_translatable_hover");
        this.hovered = el;
        el?.classList.add("o_translatable_hover");
    }

    onOver(ev) {
        this.setHovered(ev.target.closest(OWN_UI) ? null : ev.target);
    }

    onClick(ev) {
        if (ev.target.closest(OWN_UI)) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const text = textOf(ev.target);
        if (!text) {
            this.notification.add(_t("No text here to translate."), { type: "warning" });
            return;
        }
        this.dialog.add(TranslationPopup, {
            text,
            hint: hintOf(ev.target),
            lang: this.translationMode.lang,
            model: this.action.currentController?.action?.res_model || false,
            onDone: () => this.translationMode.refreshPending(),
        });
    }

    async apply() {
        const action = await this.orm.call("translation.override", "action_apply_pending", [[]]);
        await this.action.doAction(action);
        await this.translationMode.refreshPending();
    }

    openChanges() {
        this.action.doAction("custom_translate.action_translation_override");
    }
}

registry.category("main_components").add("custom_translate.TranslationModeOverlay", {
    Component: TranslationModeOverlay,
});
