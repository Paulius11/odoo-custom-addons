from odoo import _, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    user_menu_sort_ids = fields.One2many(
        "user.menu.sort",
        "user_id",
        string="Menu Preferences",
        help="User menu sorting preferences",
    )

    def write(self, vals):
        if "user_menu_sort_ids" in vals and self == self.env.user:
            # Saving the own menu order needs no write right on res.users: the
            # user.menu.sort record rules already limit the rows to the user's own.
            vals = dict(vals)
            self._fields["user_menu_sort_ids"].write(
                self, vals.pop("user_menu_sort_ids")
            )
            if not vals:
                return True
        return super().write(vals)

    def action_open_menu_config(self):
        """Open the menu configuration form for the current user"""
        self.ensure_one()
        # Apps installed since the last visit get a row too.
        self.env["user.menu.sort"].initialize_user_menus()
        return {
            "name": _("Configure Menu Order"),
            "type": "ir.actions.act_window",
            "res_model": "res.users",
            "view_mode": "form",
            "view_id": self.env.ref(
                "simple_user_menu_sort.view_user_menu_sort_config_form"
            ).id,
            "res_id": self.env.user.id,
            "target": "new",
            "context": {"form_view_initial_mode": "edit"},
        }

    def action_save_menu_order(self):
        """Dialog Save: the form saves first; reload so the app menu shows it"""
        return {"type": "ir.actions.client", "tag": "reload"}
