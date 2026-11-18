import io
import zipfile
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import Form, TransactionCase, new_test_user, tagged

MANAGER = "simple_scheduled_reports.group_scheduled_report_manager"


@tagged("post_install", "-at_install")
class TestSimpleScheduledReports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["ir.model"]._get("res.partner")
        cls.be = cls.env.ref("base.be")
        cls.fr = cls.env.ref("base.fr")
        cls.today = fields.Date.today()
        Partner = cls.env["res.partner"]
        cls.alpha = Partner.create(
            {
                "name": "SSR Alpha",
                "country_id": cls.be.id,
                "color": 1,
                "date": cls.today,
            }
        )
        cls.beta = Partner.create(
            {
                "name": "SSR Beta",
                "country_id": cls.be.id,
                "color": 2,
                "date": cls.today - timedelta(days=1),
            }
        )
        cls.gamma = Partner.create(
            {
                "name": "SSR Gamma",
                "country_id": cls.fr.id,
                "color": 5,
                "date": cls.today - timedelta(days=10),
            }
        )
        cls.recipient = Partner.create(
            {"name": "SSR Reader", "email": "reader@example.com"}
        )

    def _field(self, name):
        return self.env["ir.model.fields"]._get("res.partner", name)

    def _report(self, **vals):
        values = {
            "name": "SSR partners",
            "model_id": self.partner_model.id,
            "domain": f"[('name', 'like', 'SSR '), ('id', '!=', {self.recipient.id})]",
            "column_ids": [
                fields.Command.create(
                    {"sequence": 1, "field_id": self._field("name").id}
                ),
                fields.Command.create(
                    {"sequence": 2, "field_id": self._field("color").id}
                ),
            ],
            "recipient_partner_ids": [fields.Command.set(self.recipient.ids)],
            "email_to": "boss@example.com",
        }
        values.update(vals)
        return self.env["simple.scheduled.report"].create(values)

    def test_send_grouped_report_with_totals(self):
        report = self._report(groupby_field_id=self._field("country_id").id)
        report.action_send_now()

        mail = self.env["mail.mail"].search([("subject", "like", "SSR partners")])
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.recipient_ids, self.recipient)
        self.assertEqual(mail.email_to, "boss@example.com")
        body = mail.body_html
        for text in ("SSR Alpha", "SSR Beta", "SSR Gamma", "Belgium (2)", "France (1)"):
            self.assertIn(text, body)
        self.assertRegex(body, r">\s*3\s*<")  # Belgium subtotal 1 + 2
        self.assertRegex(body, r">\s*8\s*<")  # grand total 1 + 2 + 5

        self.assertEqual(len(mail.attachment_ids), 1)
        with zipfile.ZipFile(io.BytesIO(mail.attachment_ids.raw)) as xlsx:
            strings = xlsx.read("xl/sharedStrings.xml").decode()
        self.assertIn("SSR Gamma", strings)
        self.assertIn("France (1)", strings)

        note = report.message_ids[0]
        self.assertIn("Sent 3 rows", note.body)
        self.assertEqual(note.attachment_ids, mail.attachment_ids)
        self.assertTrue(report.last_sent)

    def test_period_filters_on_date_field(self):
        report = self._report(
            date_field_id=self._field("date").id,
            period="last",
            period_count=7,
            period_unit="day",
        )
        data = report._collect()
        names = [row[0][0] for group in data["groups"] for row in group["rows"]]
        self.assertEqual(names, ["SSR Beta"])
        report.period = "this"
        self.assertEqual(report._collect()["count"], 1)  # only Alpha is dated today

    def test_report_reads_as_owner(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        self.gamma.company_id = other_company
        owner = new_test_user(
            self.env,
            login="ssr_owner",
            groups=f"base.group_user,{MANAGER}",
            company_id=self.env.company.id,
            company_ids=[self.env.company.id],
        )
        report = self._report(user_id=owner.id)
        data = report._collect()
        self.assertEqual(data["count"], 2)
        report._send_report()
        mail = self.env["mail.mail"].search([("subject", "like", "SSR partners")])
        self.assertNotIn("SSR Gamma", mail.body_html)

    def test_manager_builds_and_sends_own_report(self):
        manager = new_test_user(
            self.env, login="ssr_builder", groups=f"base.group_user,{MANAGER}"
        )
        env = self.env(user=manager)
        # the form's pickers search models and fields as the manager
        self.assertTrue(env["ir.model"].name_search("res.partner"))
        self.assertTrue(env["ir.model.fields"].name_search("Country"))
        form = Form(env["simple.scheduled.report"])
        form.name = "SSR partners"
        form.model_id = self.partner_model
        form.domain = "[('name', 'like', 'SSR ')]"
        form.groupby_field_id = self._field("country_id")
        with form.column_ids.new() as column:
            column.field_id = self._field("name")
        form.email_to = "team@example.com"
        report = form.save()
        self.assertEqual(report.user_id, manager)
        report.action_send_now()
        mail = self.env["mail.mail"].search([("subject", "like", "SSR partners")])
        self.assertIn("Belgium (2)", mail.body_html)

    def test_manager_cannot_own_others_reports(self):
        manager = new_test_user(
            self.env, login="ssr_manager", groups=f"base.group_user,{MANAGER}"
        )
        Report = self.env["simple.scheduled.report"].with_user(manager)
        Report.create({"name": "Mine", "model_id": self.partner_model.id})
        with self.assertRaises(AccessError):
            Report.create(
                {
                    "name": "As admin",
                    "model_id": self.partner_model.id,
                    "user_id": self.env.ref("base.user_admin").id,
                }
            )

    def test_skip_if_empty(self):
        report = self._report(domain="[('id', '=', 0)]", skip_empty=True)
        self.assertFalse(report._send_report())
        self.assertFalse(
            self.env["mail.mail"].search([("subject", "like", "SSR partners")])
        )
        report.skip_empty = False
        self.assertTrue(report._send_report())

    def test_next_send(self):
        report = self._report(frequency="weekly", mon=True, send_hour=7.0)
        report.user_id.tz = "UTC"
        wednesday = datetime(2026, 11, 18, 10, 0)
        self.assertEqual(
            report._next_send_after(wednesday), datetime(2026, 11, 23, 7, 0)
        )
        report.write({"frequency": "monthly", "month_day": 31})
        self.assertEqual(
            report._next_send_after(datetime(2027, 2, 10)), datetime(2027, 2, 28, 7, 0)
        )
        report.frequency = "daily"
        self.assertEqual(
            report._next_send_after(datetime(2026, 11, 18, 6, 0)),
            datetime(2026, 11, 18, 7, 0),
        )
        report.user_id.tz = "Europe/Vilnius"  # UTC+2 in November
        self.assertEqual(
            report._next_send_after(datetime(2026, 11, 18, 6, 0)),
            datetime(2026, 11, 19, 5, 0),
        )

    def test_cron_sends_due_reports(self):
        report = self._report()
        report.next_send = fields.Datetime.now() - timedelta(minutes=1)
        self.env["simple.scheduled.report"]._cron_send_due()
        self.assertTrue(
            self.env["mail.mail"].search([("subject", "like", "SSR partners")])
        )
        self.assertGreater(report.next_send, fields.Datetime.now())
