import logging

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.simple_access_debugger.models import access_error_log

LOGGER = "odoo.addons.simple_access_debugger.models.access_error_log"
PARAM = "simple_access_debugger.log_access_errors"


@tagged("post_install", "-at_install")
class TestSimpleAccessDebugger(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="sad_user", groups="base.group_user")
        Partner = cls.env["res.partner"]
        cls.visible = Partner.create({"name": "SAD Visible"})
        cls.hidden = Partner.create({"name": "SAD Hidden", "ref": "SAD-HIDDEN"})
        cls.rule = cls.env["ir.rule"].create(
            {
                "name": "SAD hide one partner",
                "model_id": cls.env["ir.model"]._get_id("res.partner"),
                "domain_force": "[('ref', '!=', 'SAD-HIDDEN')]",
            }
        )

    def setUp(self):
        super().setUp()
        access_error_log._last_reported.clear()

    def _check(self, model, **vals):
        debugger = self.env["simple.access.debugger"].create(
            dict(
                {
                    "user_id": self.user.id,
                    "model_id": self.env["ir.model"]._get_id(model),
                },
                **vals,
            )
        )
        debugger.action_check()
        return debugger

    def test_blocked_by_record_rule(self):
        debugger = self._check("res.partner", res_id=self.hidden.id)
        self.assertEqual(debugger.verdict_state, "blocked")
        self.assertIn("SAD hide one partner", debugger.verdict)
        line = debugger.rule_line_ids.filtered(lambda r: r.rule_id == self.rule)
        self.assertTrue(line.applies)
        self.assertEqual(line.record_match, "no")
        self.assertTrue(debugger.acl_line_ids.filtered("grants"))

        debugger.res_id = self.visible.id
        debugger.action_check()
        self.assertEqual(debugger.verdict_state, "allowed")
        self.assertEqual(line.exists(), line.browse())  # lines are rebuilt
        line = debugger.rule_line_ids.filtered(lambda r: r.rule_id == self.rule)
        self.assertEqual(line.record_match, "yes")

    def test_whole_model_counts(self):
        debugger = self._check("res.partner")
        self.assertEqual(debugger.verdict_state, "allowed")
        self.assertEqual(debugger.total_count - debugger.allowed_count, 1)

    def test_blocked_by_access_rights(self):
        # only Settings users may change countries
        debugger = self._check("res.country", operation="write")
        self.assertEqual(debugger.verdict_state, "blocked")
        self.assertIn("Blocked by access rights", debugger.verdict)
        self.assertIn("Settings", debugger.verdict)
        self.assertFalse(debugger.acl_line_ids.filtered("grants"))
        settings = debugger.acl_line_ids.filtered(
            lambda r: r.group_id == self.env.ref("base.group_system")
        )
        self.assertFalse(settings.user_in_group)

    def test_all_models(self):
        debugger = self._check("res.partner")
        lines = {line.model: line for line in debugger.model_line_ids}
        self.assertTrue(lines["res.partner"].perm_read)
        self.assertFalse(lines["res.country"].perm_write)
        self.assertNotIn("mail.thread", lines)  # abstract
        action = debugger.action_open_models()
        self.assertEqual(action["domain"], [("debugger_id", "=", debugger.id)])

    def test_try_domain_as_user(self):
        domain = "[('id', '=', user.partner_id.id)]"
        debugger = self._check(
            "res.partner", res_id=self.user.partner_id.id, test_domain=domain
        )
        self.assertEqual(debugger.test_domain_count, 1)
        self.assertEqual(debugger.test_domain_match, "yes")

        line = debugger.rule_line_ids.filtered(lambda r: r.rule_id == self.rule)
        line.action_try()
        self.assertEqual(debugger.test_domain, self.rule.domain_force)

        debugger.test_domain = "[('no_such_field', '=', 1)]"
        with self.assertRaises(UserError):
            debugger.action_check()

    def test_error_log_off_by_default(self):
        hidden = self.hidden.with_user(self.user)
        with (
            self.assertNoLogs(LOGGER, level=logging.WARNING),
            self.assertRaises(AccessError),
        ):
            hidden.read(["name"])

    def test_error_log_names_rule_and_groups(self):
        self.env["ir.config_parameter"].set_param(PARAM, "True")
        hidden = self.hidden.with_user(self.user)
        with (
            self.assertLogs(LOGGER, level=logging.WARNING) as logs,
            self.assertRaises(AccessError),
        ):
            hidden.read(["name"])
        report = "\n".join(logs.output)
        self.assertIn("Access denied by record rules: read on res.partner", report)
        self.assertIn("SAD hide one partner", report)
        self.assertIn("sad_user", report)

        country = self.env.ref("base.be").with_user(self.user)
        with (
            self.assertLogs(LOGGER, level=logging.WARNING) as logs,
            self.assertRaises(AccessError),
        ):
            country.write({"name": "Belgium"})
        report = "\n".join(logs.output)
        self.assertIn("Access denied by access rights: write on res.country", report)
        self.assertIn("Groups that may write: Administration/Settings", report)

        # the same denial again within 10 minutes is not reported twice
        with (
            self.assertNoLogs(LOGGER, level=logging.WARNING),
            self.assertRaises(AccessError),
        ):
            country.write({"name": "Belgium"})
