import {BasePrinter} from "@point_of_sale/app/utils/printer/base_printer";
import {_t} from "@web/core/l10n/translation";
import {rpc} from "@web/core/network/rpc";

/**
 * An ESC/POS printer on the shop network. The browser sends the receipt image core already
 * renders to the Odoo server, which turns it into ESC/POS and writes it to the printer.
 */
export class EscPosNetworkPrinter extends BasePrinter {
    setup({printerId}) {
        super.setup(...arguments);
        this.printerId = printerId;
    }

    /** PNG keeps text edges sharp; the server makes the 1-bit raster. */
    processCanvas(canvas) {
        return canvas.toDataURL("image/png").split(",")[1];
    }

    sendPrintingJob(image) {
        return rpc("/pos_escpos_printer/print", {printer_id: this.printerId, image});
    }

    openCashbox() {
        return rpc("/pos_escpos_printer/cashbox", {printer_id: this.printerId}).catch(
            (error) => console.warn("Cash drawer not opened", error)
        );
    }

    getActionError() {
        return {
            successful: false,
            canRetry: true,
            message: {
                title: _t("Printing failed"),
                body: _t("The Odoo server could not send the job to the printer."),
            },
        };
    }

    getResultsError(printResult) {
        return {
            successful: false,
            canRetry: true,
            message: {
                title: _t("Printer not reachable"),
                body: printResult?.message || _t("The printer did not accept the job."),
            },
        };
    }
}
