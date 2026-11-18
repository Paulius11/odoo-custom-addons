from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _


class UserMenuSort(models.Model):
    _name = "user.menu.sort"
    _description = "User Menu Sort Preferences"
    _order = "sequence, id"

    user_id = fields.Many2one(
        "res.users",
        required=False,
        ondelete="cascade",
        index=True,
        default=lambda self: self.env.user,
    )
    menu_id = fields.Many2one(
        "ir.ui.menu", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(
        default=10, help="Determines the display order of menu items"
    )
    is_global_template = fields.Boolean(
        string="Global Template",
        default=False,
        help="When True, this record serves as a global template for all users",
    )

    @api.constrains("user_id", "menu_id", "is_global_template")
    def _check_unique_menu_per_user(self):
        """Ensure unique menu preferences per user and unique global templates"""
        for record in self:
            domain = [("menu_id", "=", record.menu_id.id), ("id", "!=", record.id)]

            if record.is_global_template:
                # For templates, ensure only one global template per menu
                domain.append(("is_global_template", "=", True))
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _("A global template for this menu already exists!")
                    )
            elif record.user_id:
                # For user records, ensure unique per user
                domain.append(("user_id", "=", record.user_id.id))
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _("A user can only have one sort preference per menu item!")
                    )

    @api.model
    def get_user_menu_order(self):
        """Map of menu id to sequence: the user's own rows, else the global template"""
        rows = self.search([("user_id", "=", self.env.user.id)])
        if not rows:
            # sudo: the record rules hide the template rows from regular users
            rows = self.sudo().search(
                [("is_global_template", "=", True), ("user_id", "=", False)]
            )
        return {row.menu_id.id: row.sequence for row in rows}

    def reset_user_menu_order(self):
        """Reset the user's menu order to default"""
        self.search([("user_id", "=", self.env.user.id)]).unlink()
        self.initialize_user_menus()
        return {"type": "ir.actions.client", "tag": "reload"}

    def sort_alphabetically(self):
        """Sort menu items alphabetically by menu name"""
        self.initialize_user_menus()
        user_prefs = self.search([("user_id", "=", self.env.user.id)])
        sorted_prefs = user_prefs.sorted(key=lambda p: (p.menu_id.name or "").lower())
        for sequence, pref in enumerate(sorted_prefs, start=1):
            pref.sequence = sequence * 10
        return {"type": "ir.actions.client", "tag": "reload"}

    def initialize_user_menus(self):
        """Create preferences for the root menus that don't have one yet"""
        user_id = self.env.user.id
        existing_menu_ids = (
            self.search([("user_id", "=", user_id)]).mapped("menu_id").ids
        )

        # Admin template order where it has one (sudo: record rules hide it from users),
        # otherwise the menu's own sequence, e.g. for apps installed after the template.
        template_sequence = {
            template.menu_id.id: template.sequence
            for template in self.sudo().search(
                [("is_global_template", "=", True), ("user_id", "=", False)]
            )
        }

        # Root menus this user can see that don't have a preference yet
        root_menus = self.env["ir.ui.menu"].search([("parent_id", "=", False)])
        self.create(
            [
                {
                    "user_id": user_id,
                    "menu_id": menu.id,
                    "sequence": template_sequence.get(menu.id, menu.sequence or 10),
                }
                for menu in root_menus
                if menu.id not in existing_menu_ids
            ]
        )

    def apply_to_all_users(self):
        """Make the admin's order the template and copy it to every user's rows"""
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(
                _("Only system administrators can apply menu order to all users")
            )

        admin_prefs = self.search([("user_id", "=", self.env.user.id)])
        if not admin_prefs:
            raise UserError(
                _("Open Configure Menu Order and set your own order first.")
            )
        admin_sequence_map = {pref.menu_id.id: pref.sequence for pref in admin_prefs}

        # Replace the template (user_id NULL) with the admin's current order
        self.search([("is_global_template", "=", True)]).unlink()
        self.create(
            [
                {
                    "user_id": False,
                    "menu_id": pref.menu_id.id,
                    "sequence": pref.sequence,
                    "is_global_template": True,
                }
                for pref in admin_prefs
            ]
        )

        # Users who already have rows get the admin's sequence for the same menus
        other_prefs = self.search(
            [
                ("user_id", "!=", self.env.user.id),
                ("user_id", "!=", False),
                ("menu_id", "in", list(admin_sequence_map)),
            ]
        )
        for user_pref in other_prefs:
            user_pref.sequence = admin_sequence_map[user_pref.menu_id.id]

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _(
                    "Menu order has been applied to all users. "
                    "Existing menu items have been reordered."
                ),
                "type": "success",
                "sticky": False,
            },
        }
