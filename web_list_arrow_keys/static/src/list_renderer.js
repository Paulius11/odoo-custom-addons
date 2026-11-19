/** @odoo-module **/
import {ListRenderer} from "@web/views/list/list_renderer";
import {getActiveHotkey} from "@web/core/hotkeys/hotkey_service";
import {patch} from "@web/core/utils/patch";

const VERTICAL = {arrowup: -1, arrowdown: 1, enter: 1};
const HORIZONTAL = {arrowleft: -1, arrowright: 1};

/**
 * Is the text cursor of `el` at its start (step -1) or its end (step 1)? A fully selected
 * value, as right after jumping into a cell, counts as both, like a spreadsheet cell.
 */
function caretAtEdge(el, step) {
    if (!["INPUT", "TEXTAREA"].includes(el.tagName) || el.selectionStart === null) {
        // Checkbox, button: no text cursor to move first
        return true;
    }
    const {selectionStart: start, selectionEnd: end, value} = el;
    if (start !== end && !(start === 0 && end === value.length)) {
        return false;
    }
    return step < 0 ? start === 0 : end === value.length;
}

patch(ListRenderer.prototype, {
    onCellKeydown(ev, group = null, record = null) {
        if (
            this.editedRecord &&
            record &&
            this.onArrowKey(getActiveHotkey(ev), ev.target, group, record)
        ) {
            ev.preventDefault();
            ev.stopPropagation();
            return;
        }
        return super.onCellKeydown(...arguments);
    },

    /**
     * Move to the neighbouring cell while editing. Returns true when it moved; false leaves
     * the key to the field and to core (Tab, Escape, Enter on a new or the last line).
     */
    onArrowKey(hotkey, el, group, record) {
        const list = this.props.list;
        const cell = el.closest("td");
        if (
            !cell ||
            list.model.useSampleModel ||
            (record.selected && list.model.multiEdit) ||
            el.tagName === "SELECT" ||
            el.type === "number" ||
            el.isContentEditable
        ) {
            return false;
        }
        let step = HORIZONTAL[hotkey];
        if (step) {
            step = this.isRTL ? -step : step;
            if (!caretAtEdge(el, step)) {
                return false;
            }
            const row = cell.parentElement;
            const toFocus =
                step > 0
                    ? this.findNextFocusableOnRow(row, cell)
                    : this.findPreviousFocusableOnRow(row, cell);
            if (!toFocus) {
                return false;
            }
            this.focus(toFocus);
            return true;
        }
        step = VERTICAL[hotkey];
        if (
            !step ||
            (hotkey === "enter" && (record.isNew || el.tagName === "TEXTAREA")) ||
            (el.tagName === "TEXTAREA" && !caretAtEdge(el, step))
        ) {
            return false;
        }
        const records = (group ? group.list : list).records;
        const next = records[records.indexOf(record) + step];
        if (!next) {
            return false;
        }
        const column = this.state.columns.find(
            (col) => col.name === cell.getAttribute("name")
        );
        list.leaveEditMode({validate: true}).then((left) => {
            if (left) {
                this.cellToFocus = {column, forward: true, record: next};
                list.enterEditMode(next);
            }
        });
        return true;
    },
});
