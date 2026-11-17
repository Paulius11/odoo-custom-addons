from odoo import api, fields, models, tools

METHOD_FIELDS = {
    "create": "log_create",
    "write": "log_write",
    "unlink": "log_unlink",
    "search": "log_search",
    "search_read": "log_search_read",
}


class DebugLoggerSettings(models.Model):
    _name = "debug.logger.settings"
    _description = "Debug Logger Settings"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    enable_logging = fields.Boolean(default=True)
    store_entries = fields.Boolean(string="Store Log Entries", default=True)
    max_entries = fields.Integer(
        string="Maximum Entries to Keep",
        default=1000,
        help="Older entries will be automatically deleted",
    )
    model_ids = fields.Many2many(
        "ir.model",
        string="Models to Log",
        help="Select models to log. If none selected, all models will be logged.",
    )
    entry_count = fields.Integer(
        string="Log Entries Count", compute="_compute_entry_count"
    )

    # Method selection fields
    log_create = fields.Boolean(string="Log Create Operations", default=True)
    log_write = fields.Boolean(string="Log Write Operations", default=True)
    log_unlink = fields.Boolean(string="Log Delete Operations", default=True)
    log_search = fields.Boolean(string="Log Search Operations", default=False)
    log_search_read = fields.Boolean(string="Log Search Read Operations", default=False)

    @api.model
    @tools.ormcache()
    def _get_config(self):
        """Active config as plain values, cached: read on every ORM call."""
        settings = self.sudo().search([], limit=1)
        if not settings.enable_logging:
            return None
        return {
            "store": settings.store_entries,
            "max_entries": settings.max_entries,
            "methods": frozenset(
                method for method, field in METHOD_FIELDS.items() if settings[field]
            ),
            "models": frozenset(settings.model_ids.mapped("model")),
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered("active")[-1:]._deactivate_others()
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get("active"):
            self[-1:]._deactivate_others()
        self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result

    def _deactivate_others(self):
        """Only one configuration is active: the last one created or activated."""
        self.search([("id", "not in", self.ids)]).write({"active": False})

    def activate_configuration(self):
        """Activate this configuration and deactivate others"""
        self.ensure_one()
        self.active = True
        return True

    def _compute_entry_count(self):
        """Compute the number of log entries"""
        for record in self:
            if record.store_entries:
                record.entry_count = self.env["debug.logger.entry"].search_count([])
            else:
                record.entry_count = 0

    def action_view_log_entries(self):
        """Action to view log entries"""
        return self.env["ir.actions.act_window"]._for_xml_id(
            "debug_logger.action_debug_logger_entries"
        )
