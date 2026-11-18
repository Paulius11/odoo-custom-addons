from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged

from odoo.addons.mail.tests.common import mail_new_test_user

EMAIL = """From: Jane Customer <jane@customer.example>
To: nobody@company.example
Subject: {subject}
Message-ID: {msgid}
{extra}Date: Tue, 17 Nov 2026 10:00:00 +0000
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="b1"

--b1
Content-Type: text/plain; charset=utf-8

Please send me the invoice.
--b1
Content-Type: text/plain; name="order.txt"
Content-Disposition: attachment; filename="order.txt"

order 42
--b1--
"""


def email_source(
    subject="Invoice please", msgid="<lost-1@customer.example>", **headers
):
    extra = "".join(f"{key}: {value}\n" for key, value in headers.items())
    return EMAIL.format(subject=subject, msgid=msgid, extra=extra)


@tagged("post_install", "-at_install")
class TestMailLost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Thread = cls.env["mail.thread"]
        cls.Lost = cls.env["mail.lost"]
        cls.partner = cls.env["res.partner"].create({"name": "Acme Ltd"})
        cls.manager = mail_new_test_user(
            cls.env,
            login="lost_manager",
            name="Lost Manager",
            groups="base.group_user,base.group_partner_manager,"
            "mail_lost.group_mail_lost_manager",
            notification_type="inbox",
        )

    def receive(self, source, model=None):
        """What fetchmail and the mailgate script do with every incoming email."""
        return self.Thread.message_process(model, source)

    def route(self, lost, **values):
        wizard = Form(
            self.env["mail.lost.route"]
            .with_user(self.manager)
            .with_context(default_lost_ids=lost.ids)
        )
        for name, value in values.items():
            if name == "record_ref":
                value = f"{value._name},{value.id}"
            setattr(wizard, name, value)
        return wizard.save().action_confirm()

    # ------------------------------------------------------------ catching

    def test_unrouted_email_is_kept_not_bounced(self):
        with patch.object(type(self.Thread), "_routing_create_bounce_email") as bounce:
            lost = self.Lost.browse(self.receive(email_source()))
        bounce.assert_not_called()
        self.assertEqual(lost._name, "mail.lost")
        self.assertEqual(lost.name, "Invoice please")
        self.assertIn("<jane@customer.example>", lost.email_from)
        self.assertEqual(lost.author_id, self.env["res.partner"])  # unknown sender
        self.assertEqual(lost.email_to, "nobody@company.example")
        self.assertEqual(lost.state, "new")
        self.assertIn("No possible route", lost.reason)
        self.assertTrue(lost.raw_email)
        message = lost.message_ids.filtered(lambda m: m.message_type == "email")
        self.assertIn("Please send me the invoice.", message.body)
        self.assertEqual(message.attachment_ids.mapped("name"), ["order.txt"])

    def test_same_email_twice_is_kept_once(self):
        self.receive(email_source())
        self.assertFalse(self.receive(email_source()))
        self.assertEqual(self.Lost.search_count([]), 1)

    def test_managers_are_notified(self):
        lost = self.Lost.browse(self.receive(email_source()))
        self.assertIn(self.manager.partner_id, lost.message_partner_ids)
        notified = self.env["mail.notification"].search(
            [("res_partner_id", "=", self.manager.partner_id.id)]
        )
        self.assertIn(lost.message_ids[0], notified.mail_message_id)

    def test_fallback_model_still_wins(self):
        partner_id = self.receive(email_source(), model="res.partner")
        self.assertEqual(
            self.env["res.partner"].browse(partner_id).name, "Invoice please"
        )
        self.assertFalse(self.Lost.search_count([]))

    def test_alias_still_wins(self):
        self.env["mail.alias"].create(
            {
                "alias_name": "nobody",
                "alias_model_id": self.env["ir.model"]._get_id("res.partner"),
                "alias_incoming_local": True,
            }
        )
        partner_id = self.receive(email_source())
        self.assertEqual(
            self.env["res.partner"].browse(partner_id).name, "Invoice please"
        )
        self.assertFalse(self.Lost.search_count([]))

    def test_reply_to_a_record_still_wins(self):
        sent = self.partner.message_post(body="Your order", message_type="comment")
        self.receive(
            email_source(
                msgid="<reply-1@customer.example>", **{"In-Reply-To": sent.message_id}
            )
        )
        self.assertIn("Please send me the invoice.", self.partner.message_ids[0].body)
        self.assertFalse(self.Lost.search_count([]))

    def test_reply_to_a_lost_email_is_lost_on_its_own(self):
        first = self.Lost.browse(self.receive(email_source()))
        second = self.Lost.browse(
            self.receive(
                email_source(
                    subject="Re: Invoice please",
                    msgid="<lost-2@customer.example>",
                    **{"In-Reply-To": "<lost-1@customer.example>"},
                )
            )
        )
        self.assertEqual(second._name, "mail.lost")
        self.assertNotEqual(first, second)
        self.assertEqual(
            len(first.message_ids.filtered(lambda m: m.message_type == "email")), 1
        )

    # ------------------------------------------------------------ routing

    def test_route_to_existing_record(self):
        lost = self.Lost.browse(self.receive(email_source()))
        action = self.route(lost, record_ref=self.partner)
        self.assertEqual(
            (action["res_model"], action["res_id"]), ("res.partner", self.partner.id)
        )
        message = self.partner.message_ids.filtered(lambda m: m.message_type == "email")
        self.assertIn("Please send me the invoice.", message.body)
        self.assertEqual(message.attachment_ids.mapped("name"), ["order.txt"])
        self.assertEqual(message.attachment_ids.res_id, self.partner.id)
        self.assertEqual(lost.state, "routed")
        self.assertEqual(lost.target_ref, self.partner)

    def test_route_creates_record(self):
        lost = self.Lost.browse(self.receive(email_source()))
        action = self.route(lost, mode="new", model="res.partner")
        partner = self.env["res.partner"].browse(action["res_id"])
        self.assertEqual(partner.name, "Invoice please")
        self.assertIn(
            "Please send me the invoice.", partner.message_ids.mapped("body")[-1]
        )
        self.assertEqual(lost.target_ref, partner)

    def test_reply_after_routing_reaches_the_record(self):
        lost = self.Lost.browse(self.receive(email_source()))
        self.route(lost, record_ref=self.partner)
        self.receive(
            email_source(
                subject="Re: Invoice please",
                msgid="<lost-2@customer.example>",
                **{"In-Reply-To": "<lost-1@customer.example>"},
            )
        )
        self.assertEqual(self.Lost.search_count([]), 1)
        self.assertEqual(self.partner.message_ids[0].subject, "Re: Invoice please")

    def test_route_several_at_once(self):
        lost = self.Lost.browse(
            [
                self.receive(email_source(msgid=f"<batch-{n}@customer.example>"))
                for n in range(3)
            ]
        )
        action = self.route(lost, record_ref=self.partner)
        self.assertEqual(action["res_id"], self.partner.id)
        self.assertEqual(set(lost.mapped("state")), {"routed"})
        self.assertEqual(
            len(self.partner.message_ids.filtered(lambda m: m.message_type == "email")),
            3,
        )

    def test_route_needs_post_access_on_target(self):
        blocked = self.env["mail.blacklist"].create({"email": "spam@example.com"})
        lost = self.Lost.browse(self.receive(email_source()))
        with self.assertRaises(AccessError):
            self.route(lost, record_ref=blocked)
        with self.assertRaises(AccessError):
            self.route(lost, mode="new", model="mail.blacklist")
        self.assertEqual(lost.state, "new")

    def test_route_only_once(self):
        lost = self.Lost.browse(self.receive(email_source()))
        self.route(lost, record_ref=self.partner)
        with self.assertRaises(UserError):
            lost._route_to("res.partner", self.partner.id)

    def test_route_without_original(self):
        lost = self.Lost.browse(self.receive(email_source()))
        lost.raw_email = False
        with self.assertRaises(UserError):
            lost._route_to("res.partner", self.partner.id)

    def test_ignore_and_reopen(self):
        lost = self.Lost.browse(self.receive(email_source())).with_user(self.manager)
        lost.action_ignore()
        self.assertEqual(lost.state, "ignored")
        self.assertFalse(lost.action_route()["context"]["default_lost_ids"])
        lost.action_reopen()
        self.assertEqual(lost.state, "new")

    def test_only_managers_see_lost_emails(self):
        lost = self.Lost.browse(self.receive(email_source()))
        user = mail_new_test_user(
            self.env, login="plain_user", groups="base.group_user"
        )
        with self.assertRaises(AccessError):
            lost.with_user(user).read(["name"])
        self.assertEqual(lost.with_user(self.manager).name, "Invoice please")

    def test_targets_exclude_lost_and_abstract_models(self):
        models = dict(self.Lost._selection_target_model())
        self.assertIn("res.partner", models)
        self.assertNotIn("mail.lost", models)
        self.assertNotIn("mail.thread", models)
