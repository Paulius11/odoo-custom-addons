from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

MODEL = "res.partner"


@tagged("post_install", "-at_install")
class TestColumnPreset(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Preset = cls.env["ir.listview.column.preset"]
        cls.user = new_test_user(cls.env, login="preset_user", groups="base.group_user")
        cls.other = new_test_user(
            cls.env, login="preset_other", groups="base.group_user"
        )
        cls.manager = new_test_user(
            cls.env,
            login="preset_manager",
            groups="base.group_user,web_listview_column_presets.group_shared_presets",
        )

    def _presets(self, user):
        return {p["name"]: p for p in self.Preset.with_user(user).get_presets(MODEL)}

    def test_personal_preset(self):
        Preset = self.Preset.with_user(self.user)
        saved = Preset.save_preset(MODEL, "Mine", ["email", "phone"])
        self.assertEqual(saved["column_fields"], ["email", "phone"])
        mine = self._presets(self.user)["Mine"]
        self.assertTrue(mine["is_own"])
        self.assertFalse(mine["is_shared"])
        self.assertEqual(mine["column_fields"], ["email", "phone"])
        self.assertNotIn("Mine", self._presets(self.other))
        self.assertEqual(Preset.get_presets("res.users"), [])
        Preset.browse(saved["id"]).delete_preset()
        self.assertNotIn("Mine", self._presets(self.user))

    def test_shared_preset(self):
        saved = self.Preset.with_user(self.manager).save_preset(
            MODEL, "Team", ["email"], is_shared=True
        )
        team = self._presets(self.user)["Team"]
        self.assertTrue(team["is_shared"])
        self.assertFalse(team["is_own"])
        shared = self.Preset.with_user(self.user).browse(saved["id"])
        with self.assertRaises(AccessError):
            shared.delete_preset()
        with self.assertRaises(AccessError):
            shared.unlink()
        with self.assertRaises(AccessError):
            shared.write({"name": "Renamed"})
        self.Preset.with_user(self.manager).browse(saved["id"]).delete_preset()
        self.assertNotIn("Team", self._presets(self.user))

    def test_user_cannot_make_shared_or_foreign_presets(self):
        Preset = self.Preset.with_user(self.user)
        with self.assertRaises(AccessError):
            Preset.save_preset(MODEL, "Team", ["email"], is_shared=True)
        # The same through plain RPC create, past save_preset's own check
        for user_id in (False, self.other.id):
            with self.assertRaises(AccessError):
                Preset.create(
                    {
                        "name": "Sneaky",
                        "model_id": MODEL,
                        "user_id": user_id,
                        "column_fields": "[]",
                    }
                )

    def test_cannot_delete_other_users_preset(self):
        saved = self.Preset.with_user(self.other).save_preset(
            MODEL, "Theirs", ["email"]
        )
        with self.assertRaises(AccessError):
            self.Preset.with_user(self.user).browse(saved["id"]).delete_preset()
