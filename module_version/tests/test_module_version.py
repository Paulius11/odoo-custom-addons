import json
from contextlib import contextmanager
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.base.models.ir_module import Module


@tagged("post_install", "-at_install")
class TestModuleVersion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Module = cls.env["ir.module.module"]
        cls.History = cls.env["module.upgrade.history"]
        cls.module = cls.Module.search([("name", "=", "module_version")])
        cls.disk = cls.module.installed_version
        cls.old = "17.0.0.0.1"

    def _last_operation(self, module):
        return self.History.search([("module_id", "=", module.id)], limit=1)

    def _assert_filter(self, field):
        modules = self.Module.search([("state", "=", "installed")])
        expected = modules.filtered(field)
        self.assertIn(self.module, expected)
        installed = [("state", "=", "installed")]
        for domain, result in (
            ([(field, "=", True)], expected),
            ([(field, "!=", False)], expected),
            ([(field, "=", False)], modules - expected),
            ([(field, "!=", True)], modules - expected),
        ):
            found = self.Module.search(installed + domain)
            self.assertEqual(set(found.ids), set(result.ids), domain)

    def test_filter_updates_available(self):
        self.module.latest_version = self.old
        self.env.flush_all()
        self.env.invalidate_all()
        self._assert_filter("has_version_upgrade")

    def test_filters_new_and_upgraded(self):
        entry = {
            "version": self.disk,
            "since": fields.Datetime.now().isoformat(),
            "is_new": True,
            "upgraded_from": self.old,
        }
        self.env["ir.config_parameter"].sudo().set_param(
            "module_version.installed_snapshot", json.dumps({"module_version": entry})
        )
        self.env.invalidate_all()
        self._assert_filter("is_newly_added")
        self._assert_filter("is_recently_upgraded")

    def test_upgrade_history_is_old_to_new(self):
        self.module.latest_version = self.old
        self.module.button_upgrade()
        record = self._last_operation(self.module)
        self.assertEqual(record.from_version, self.old)
        self.assertEqual(record.to_version, self.disk)

    def test_uninstall_history_has_the_running_version(self):
        self.module.latest_version = self.old
        self.module.button_uninstall()
        self.assertEqual(self._last_operation(self.module).from_version, self.old)

    def test_install_history_has_the_version_on_disk(self):
        module = self.Module.search([("name", "=", "barcodes")])
        if module.state != "uninstalled":
            self.skipTest("barcodes is already installed")
        expected = module.installed_version
        module.button_install()
        self.assertEqual(self._last_operation(module).to_version, expected)

    def test_failure_survives_the_rollback(self):
        self.module.latest_version = self.old

        def fail(records):
            raise UserError("<img src=x onerror=alert(1)>")

        for operation in ("upgrade", "uninstall"):
            hooks = self.env.cr.postrollback
            hooks.clear()
            with patch.object(Module, f"button_immediate_{operation}", fail):
                try:
                    getattr(self.module, f"button_immediate_{operation}")()
                except UserError:
                    pass
                else:
                    self.fail("the error must reach the user")
            self.assertTrue(hooks._funcs, "nothing is kept for after the rollback")

            @contextmanager
            def same_cursor(*args, **kwargs):
                yield self.env.cr

            with patch.object(type(self.env.registry), "cursor", same_cursor):
                hooks.run()
            record = self._last_operation(self.module)
            self.assertEqual(record.status, "failed")
            self.assertEqual(record.operation_type, operation)
            self.assertEqual(record.from_version, self.old)
            self.assertNotIn("<img", str(record.notes))

    def test_update_list_shows_the_module_name(self):
        found = {"sale_x": {"display_name": "Nice Module Name"}}
        with patch.object(
            type(self.Module), "get_modules_need_update", lambda records: found
        ):
            self.Module.action_check_updates_ui()
        self.env.flush_all()
        self.env.invalidate_all()  # as the list view reads it
        rows = self.env["ir.module.update.info"].search([]).read()
        self.assertIn("Nice Module Name", str(rows))
