/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class SavePresetDialog extends Component {
    static template = "web_listview_column_presets.SavePresetDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        onSave: Function,
        canShare: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            name: "",
            isShared: false,
        });
    }

    get canShare() {
        return this.props.canShare !== false;
    }

    get dialogTitle() {
        return _t("Save Column Preset");
    }

    get presetPlaceholder() {
        return _t("Enter preset name...");
    }

    get presetNameLabel() {
        return _t("Preset Name");
    }

    get shareLabel() {
        return _t("Share with all users");
    }

    get saveLabel() {
        return _t("Save");
    }

    get cancelLabel() {
        return _t("Cancel");
    }

    onNameChange(ev) {
        this.state.name = ev.target.value;
    }

    onSharedChange(ev) {
        this.state.isShared = ev.target.checked;
    }

    async onSave() {
        if (!this.state.name.trim()) {
            return;
        }
        await this.props.onSave({
            name: this.state.name.trim(),
            isShared: this.state.isShared,
        });
        this.props.close();
    }

    onCancel() {
        this.props.close();
    }
}
