from odoo import fields, models


class IrModuleUpdateInfo(models.TransientModel):
    _name = "ir.module.update.info"
    _description = "Module Update Information"

    name = fields.Char("Technical Name", readonly=True)
    display_name = fields.Char("Module Name", readonly=True)
    installed_version = fields.Char("Installed Version", readonly=True)
    available_version = fields.Char("Available Version", readonly=True)
