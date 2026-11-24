import {EscPosNetworkPrinter} from "@simple_pos_escpos_printer/app/escpos_printer";
import {HardwareProxy} from "@point_of_sale/app/services/hardware_proxy_service";
import {PosStore} from "@point_of_sale/app/services/pos_store";
import {patch} from "@web/core/utils/patch";

patch(PosStore.prototype, {
    /** Preparation printers of our type */
    createPrinter(config) {
        if (config.printer_type === "escpos_network") {
            return new EscPosNetworkPrinter({printerId: config.id});
        }
        return super.createPrinter(...arguments);
    },

    /** The receipt printer chosen in the POS settings, in place of an IoT or ePOS one */
    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        const printerId = this.config.raw.escpos_receipt_printer_id;
        if (printerId) {
            this.hardwareProxy.printer = new EscPosNetworkPrinter({printerId});
        }
        return result;
    },
});

patch(HardwareProxy.prototype, {
    /** Core opens the drawer only with an IoT box or an ePOS printer connected */
    async openCashbox(action = false) {
        if (!(this.printer instanceof EscPosNetworkPrinter)) {
            return super.openCashbox(...arguments);
        }
        if (this.pos.config.iface_cashdrawer) {
            this.printer.openCashbox();
            if (action) {
                this.pos.logEmployeeMessage(action, "CASH_DRAWER_ACTION");
            }
        }
    },
});
