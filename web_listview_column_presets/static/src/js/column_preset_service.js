/** @odoo-module **/

import { registry } from "@web/core/registry";
import { memoize } from "@web/core/utils/functions";

export const columnPresetService = {
    dependencies: ["orm"],

    start(env, { orm }) {
        const getPresets = async (modelName, parentModel = null, relationalField = null) => {
            return await orm.call(
                "ir.listview.column.preset",
                "get_presets",
                [modelName, parentModel, relationalField]
            );
        };

        const savePreset = async (modelName, name, columns, isShared = false, parentModel = null, relationalField = null) => {
            return await orm.call(
                "ir.listview.column.preset",
                "save_preset",
                [modelName, name, columns, isShared, parentModel, relationalField]
            );
        };

        const deletePreset = async (presetId) => {
            return await orm.call(
                "ir.listview.column.preset",
                "delete_preset",
                [[presetId]]
            );
        };

        return {
            getPresets,
            savePreset,
            deletePreset,
        };
    },
};

registry.category("services").add("columnPreset", columnPresetService);
