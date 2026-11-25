from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    access_debugger_log_errors = fields.Boolean(
        "Log Access Errors",
        config_parameter="simple_access_debugger.log_access_errors",
    )
