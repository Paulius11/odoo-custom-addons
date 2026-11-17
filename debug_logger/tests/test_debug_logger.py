import logging

from odoo.tests import TransactionCase, tagged

LOGGER = "odoo.addons.debug_logger.models.base_logger"


@tagged("post_install", "-at_install")
class TestDebugLogger(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env.ref("debug_logger.default_debug_logger_settings")
        cls.Entry = cls.env["debug.logger.entry"]
        cls.partner = cls.env["res.partner"].create({"name": "Logger Test"})

    def _enable(self, **vals):
        self.settings.write({"enable_logging": True, "store_entries": True, **vals})

    def test_off_by_default(self):
        self.assertFalse(self.settings.enable_logging)
        count = self.Entry.search_count([])
        self.partner.write({"name": "Still quiet"})
        self.assertEqual(self.Entry.search_count([]), count)

    def test_write_is_logged_and_stored(self):
        self._enable()
        with self.assertLogs(LOGGER, level=logging.INFO) as logs:
            self.partner.name = "Renamed"  # caller must skip fields.py __set__
        self.assertIn("Model: res.partner", logs.output[0])
        entry = self.Entry.search([("model", "=", "res.partner")], limit=1)
        self.assertEqual(entry.name, "WRITE")
        old = f"old_values: {{{self.partner.id}: {{'name': 'Logger Test'}}}}"
        self.assertIn(old, entry.data)
        self.assertIn("test_debug_logger.py", entry.caller_info)

    def test_secrets_masked(self):
        self._enable(model_ids=[(6, 0, self.env.ref("base.model_res_users").ids)])
        with self.assertLogs(LOGGER, level=logging.INFO) as logs:
            self.env["res.users"].create(
                {"name": "Masked", "login": "masked_user", "password": "s3cret-pw"}
            )
        self.assertNotIn("s3cret-pw", "".join(logs.output))
        self.assertIn("'password': '***'", logs.output[0])

    def test_search_read_keeps_read_kwargs(self):
        self._enable(log_search_read=True)
        rows = self.env["res.partner"].search_read(
            [("id", "=", self.partner.id)], ["parent_id"], load=False
        )
        self.assertEqual(rows[0]["parent_id"], False)

    def test_model_filter(self):
        self._enable(model_ids=[(6, 0, self.env.ref("base.model_res_partner").ids)])
        count = self.Entry.search_count([])
        self.env["res.partner.category"].create({"name": "Not logged"})
        self.assertEqual(self.Entry.search_count([]), count)
        self.partner.write({"name": "Logged"})
        self.assertEqual(self.Entry.search_count([]), count + 1)

    def test_cleanup_keeps_newest(self):
        self._enable(max_entries=2)
        for name in ("a", "b", "c"):
            self.partner.write({"name": name})
        self.assertEqual(self.Entry.search_count([]), 2)

    def test_one_active_config(self):
        new = self.settings.create({"name": "Second"})
        self.assertFalse(self.settings.active)
        self.settings.activate_configuration()
        self.assertTrue(self.settings.active)
        self.assertFalse(new.active)
