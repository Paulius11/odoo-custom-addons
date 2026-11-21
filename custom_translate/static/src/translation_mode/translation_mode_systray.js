/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class TranslationModeSystray extends Component {
    static template = "custom_translate.TranslationModeSystray";
    static props = {};

    get title() {
        return this.state.enabled
            ? _t("Turn off translation mode")
            : _t("Translation mode: click any text to translate it");
    }

    setup() {
        this.translationMode = useService("translationMode");
        this.state = useState(this.translationMode.state);
    }
}

registry
    .category("systray")
    .add("custom_translate.translation_mode", { Component: TranslationModeSystray }, { sequence: 90 });
