/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart } from "@odoo/owl";
import { SavePresetDialog } from "@web_listview_column_presets/js/save_preset_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Column presets at the top of the optional-columns dropdown (the gear icon),
 * in standalone lists and in embedded one2many/many2many lists.
 * The entries are rendered by web_listview_column_presets.ListRenderer.
 */
patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.columnPresetService = useService("columnPreset");
        this.dialogService = useService("dialog");
        this.notificationService = useService("notification");
        const user = useService("user");
        this.presetState = useState({presets: [], canShare: false});
        onWillStart(async () => {
            if (!this.hasOptionalFields) {
                return;
            }
            [this.presetState.canShare] = await Promise.all([
                user.hasGroup("web_listview_column_presets.group_shared_presets"),
                this.loadColumnPresets(),
            ]);
        });
    },

    async loadColumnPresets() {
        try {
            this.presetState.presets = await this.columnPresetService.getPresets(
                this.props.list.resModel
            );
        } catch (e) {
            console.error("[ColumnPresets] Failed to load presets:", e);
            this.presetState.presets = [];
        }
    },

    get optionalFieldNames() {
        return this.allColumns
            .filter((col) => col.optional && !this.evalColumnInvisible(col.column_invisible))
            .map((col) => col.name);
    },

    canDeletePreset(preset) {
        return preset.is_own || (this.presetState.canShare && preset.is_shared);
    },

    onSaveColumnPreset() {
        const columns = this.optionalFieldNames.filter(
            (name) => this.optionalActiveFields[name]
        );
        this.dialogService.add(SavePresetDialog, {
            canShare: this.presetState.canShare,
            onSave: async ({name, isShared}) => {
                try {
                    await this.columnPresetService.savePreset(
                        this.props.list.resModel,
                        name,
                        columns,
                        isShared
                    );
                    await this.loadColumnPresets();
                } catch (e) {
                    this.notificationService.add(
                        _t("Failed to save preset: %s", e.data?.message || e.message),
                        {type: "danger"}
                    );
                }
            },
        });
    },

    onApplyColumnPreset(preset) {
        // Same steps as core toggleOptionalField(), for every optional column at once
        for (const name of this.optionalFieldNames) {
            this.optionalActiveFields[name] = preset.column_fields.includes(name);
        }
        if (this.props.onOptionalFieldsChanged) {
            this.props.onOptionalFieldsChanged(this.optionalActiveFields);
        }
        this.state.columns = this.getActiveColumns(this.props.list);
        this.saveOptionalActiveFields();
    },

    onDeleteColumnPreset(preset) {
        this.dialogService.add(ConfirmationDialog, {
            title: _t("Delete preset"),
            body: _t("Delete the preset “%s”?", preset.name),
            confirmLabel: _t("Delete"),
            confirmClass: "btn-danger",
            confirm: async () => {
                try {
                    await this.columnPresetService.deletePreset(preset.id);
                } catch (e) {
                    this.notificationService.add(
                        _t("Failed to delete preset: %s", e.data?.message || e.message),
                        {type: "danger"}
                    );
                }
                await this.loadColumnPresets();
            },
            cancel: () => {},
        });
    },
});
