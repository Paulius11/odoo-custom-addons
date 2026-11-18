from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestSimpleUserMenuSort(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        action = cls.env.ref("base.action_partner_form")
        cls.menus = cls.env["ir.ui.menu"].create(
            [
                {
                    "name": name,
                    "action": f"ir.actions.act_window,{action.id}",
                    "sequence": 900 + i,
                }
                for i, name in enumerate(("Menu A", "Menu B", "Menu C"))
            ]
        )
        cls.admin = cls.env.ref("base.user_admin")
        cls.user = new_test_user(cls.env, "ums_user", groups="base.group_user")
        cls.Sort = cls.env["user.menu.sort"]

    def _order(self, user):
        """Ids of the test menus in the order the user's app menu shows them."""
        menus = self.env["ir.ui.menu"].with_user(user).load_menus(False)
        return [i for i in menus["root"]["children"] if i in self.menus.ids]

    def _reverse_rows(self, user):
        rows = self.Sort.with_user(user).search(
            [("user_id", "=", user.id), ("menu_id", "in", self.menus.ids)]
        )
        self.assertEqual(len(rows), 3)
        return [
            (1, row.id, {"sequence": 100 - row.menu_id.sequence % 900}) for row in rows
        ]

    def test_user_saves_own_order_from_dialog(self):
        self.user.with_user(self.user).action_open_menu_config()
        self.user.with_user(self.user).write(
            {"user_menu_sort_ids": self._reverse_rows(self.user)}
        )
        self.assertEqual(self._order(self.user), self.menus.ids[::-1])

    def test_user_cannot_change_others_rows(self):
        self.Sort.with_user(self.admin).initialize_user_menus()
        with self.assertRaises(AccessError):
            self.user.with_user(self.user).write(
                {"user_menu_sort_ids": self._reverse_rows(self.admin)}
            )
        with self.assertRaises(AccessError):
            self.admin.with_user(self.user).write({"user_menu_sort_ids": []})

    def test_new_user_follows_admin_template(self):
        self.Sort.with_user(self.admin).initialize_user_menus()
        self.admin.write({"user_menu_sort_ids": self._reverse_rows(self.admin)})
        self.Sort.with_user(self.admin).apply_to_all_users()
        newbie = new_test_user(self.env, "ums_newbie", groups="base.group_user")
        self.assertEqual(self._order(newbie), self.menus.ids[::-1])

    def test_app_installed_after_template_joins_on_open(self):
        self.Sort.with_user(self.admin).initialize_user_menus()
        self.Sort.with_user(self.admin).apply_to_all_users()
        late = self.menus[0].copy({"name": "Menu Late"})
        self.user.with_user(self.user).action_open_menu_config()
        self.assertTrue(
            self.Sort.search_count(
                [("user_id", "=", self.user.id), ("menu_id", "=", late.id)]
            )
        )
