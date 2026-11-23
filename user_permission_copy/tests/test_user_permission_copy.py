from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestUserPermissionCopy(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = new_test_user(cls.env, login="copy_source")
        cls.target = new_test_user(cls.env, login="copy_target")
        cls.boss = new_test_user(
            cls.env, login="copy_boss", groups="base.group_user,base.group_system"
        )

    def test_cannot_copy_onto_yourself(self):
        source = self.source.with_user(self.boss)
        with self.assertRaises(UserError):
            source.copy_permissions_to_user(self.boss.id)
        self.assertTrue(self.boss.has_group("base.group_system"))

    def test_wizard_refuses_yourself(self):
        wizard = self.env["user.permission.copy.wizard"].with_user(self.boss)
        with self.assertRaises(ValidationError):
            wizard.create(
                {"source_user_id": self.source.id, "target_user_id": self.boss.id}
            )

    def test_cancel_does_not_validate(self):
        view = self.env.ref(
            "user_permission_copy.view_user_permission_copy_wizard_form"
        )
        arch = etree.fromstring(view.arch)
        self.assertTrue(arch.xpath("//footer/button[@special='cancel']"))

    def test_copy_closes_the_dialog(self):
        source = self.source.with_user(self.boss)
        action = source.copy_permissions_to_user(self.target.id)
        self.assertEqual(self.target.group_ids, self.source.group_ids)
        self.assertEqual(
            action["params"].get("next"), {"type": "ir.actions.act_window_close"}
        )

    def test_contact_tags_are_not_permissions(self):
        tag = self.env["res.partner.category"].create({"name": "Keep me"})
        self.target.partner_id.category_id = tag
        self.source.copy_permissions_to_user(self.target.id)
        self.assertEqual(self.target.partner_id.category_id, tag)
