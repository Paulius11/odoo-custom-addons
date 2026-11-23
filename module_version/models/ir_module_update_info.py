from odoo import fields, models


class IrModuleUpdateInfo(models.TransientModel):
    _name = "ir.module.update.info"
    _description = "Module Update Information"

    name = fields.Char("Technical Name", readonly=True)
    module_title = fields.Char("Module Name", readonly=True)  # display_name is computed by the ORM
    installed_version = fields.Char("Installed Version", readonly=True)
    available_version = fields.Char("Available Version", readonly=True)
