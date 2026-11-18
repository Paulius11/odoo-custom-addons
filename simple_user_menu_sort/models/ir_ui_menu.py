from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def load_menus(self, debug):
        """Root apps in the user's order; apps without a row keep theirs, last"""
        menus = super().load_menus(debug)
        order = self.env["user.menu.sort"].get_user_menu_order()
        if order and "root" in menus:
            children = sorted(
                menus["root"]["children"],
                key=lambda menu_id: (menu_id not in order, order.get(menu_id, 0)),
            )
            # New dicts: super() returns its ormcache entry, which must not change
            menus = dict(menus, root=dict(menus["root"], children=children))
        return menus
