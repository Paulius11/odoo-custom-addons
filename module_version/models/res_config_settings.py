from odoo import _, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_check_updates_ui(self):
        """Check for module updates and display them in the UI."""
        IrModule = self.env["ir.module.module"]
        UpdateInfo = self.env["ir.module.update.info"]

        # Clear old records
        UpdateInfo.search([]).unlink()

        # Get modules that need updates
        modules_to_update = IrModule.get_modules_need_update()

        if not modules_to_update:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Module Updates"),
                    "message": _("All modules are up to date!"),
                    "type": "success",
                    "sticky": False,
                },
            }

        # Create records for display
        for name, info in modules_to_update.items():
            UpdateInfo.create(
                {
                    "name": name,
                    "display_name": info.get("display_name", name),
                    "installed_version": info.get("version_local_running", ""),
                    "available_version": info.get("version_remote", ""),
                }
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Available Module Updates"),
            "res_model": "ir.module.update.info",
            "view_mode": "tree",
            "target": "new",
        }
