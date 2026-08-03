/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PopoverController } from "@web/core/popover/popover_controller";

/**
 * Defensive guard against a crash loop in the core popover controller.
 *
 * PopoverController registers a global "pointerdown" listener in setup(), i.e.
 * before its child Popover is mounted, and unconditionally dereferences
 * this.popoverRef.el in isInside(). Whenever the popover is not (or no longer)
 * mounted while the controller is alive - async onWillStart in the popover
 * content, or a popover node detached outside of Owl - the ref is null and
 * every click throws "Cannot read properties of null (reading 'contains')".
 * The error dialog is itself clickable, so each click on it raises again and
 * stacks another dialog.
 *
 * Optional chaining makes the click count as "outside", which closes the
 * stale popover instead of crashing.
 */
patch(PopoverController.prototype, {
    isInside(target) {
        if (this.props.target?.contains(target) || this.popoverRef?.el?.contains(target)) {
            return true;
        }
        return [...this.subPopovers].some((p) => p.isInside(target));
    },
});
