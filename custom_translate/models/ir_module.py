from odoo import models


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def _update_translations(self, filter_lang=None, overwrite=False):
        res = super()._update_translations(filter_lang=filter_lang, overwrite=overwrite)
        # at runtime only (Settings > Languages > Update); during module loading
        # _register_hook re-applies once everything is loaded
        if self.pool.ready:
            self.env["translation.override"]._reapply_db()
        return res
