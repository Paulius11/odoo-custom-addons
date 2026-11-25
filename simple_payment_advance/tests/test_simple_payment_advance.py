from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form, new_test_user, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentAdvance(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env["account.account"]
        cls.customer_advances = Account.create(
            {
                "name": "Customer Advances",
                "code": "219000",
                "account_type": "liability_payable",
                "reconcile": True,
            }
        )
        cls.vendor_prepayments = Account.create(
            {
                "name": "Vendor Prepayments",
                "code": "139000",
                "account_type": "asset_receivable",
                "reconcile": True,
            }
        )
        cls.company = cls.env.company
        cls.company.write(
            {
                "advance_customer_account_id": cls.customer_advances.id,
                "advance_vendor_account_id": cls.vendor_prepayments.id,
            }
        )
        cls.bank = cls.company_data["default_journal_bank"]
        cls.billing = new_test_user(
            cls.env,
            login="advance_billing",
            groups="account.group_account_invoice",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )

    # ------------------------------------------------------------ helpers

    def advance(self, partner, amount, kind="customer", date=None, user=None):
        Payment = self.env["account.payment"].with_user(user or self.env.user)
        payment = Payment.create(
            {
                "is_advance": True,
                "payment_type": "inbound" if kind == "customer" else "outbound",
                "partner_type": kind,
                "partner_id": partner.id,
                "amount": amount,
                "date": date or fields.Date.today(),
                "journal_id": self.bank.id,
            }
        )
        payment.action_post()
        return payment

    def invoice(self, move_type, partner, amount, currency=None):
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "currency_id": (currency or self.company.currency_id).id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Office chairs",
                            "quantity": 1,
                            "price_unit": amount,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        move.action_post()
        return move

    def apply(self, move, payment=None, amount=None, user=None):
        Wizard = self.env["account.advance.apply"].with_user(user or self.env.user)
        form = Form(Wizard.with_context(default_move_id=move.id))
        if payment:
            form.payment_id = payment
        if amount is not None:
            form.amount = amount
        form.save().action_apply()
        return self.env["account.move"].search(
            [("advance_payment_id", "!=", False)], order="id desc", limit=1
        )

    # ------------------------------------------------------------ setup

    def test_accountant_sets_accounts_in_settings(self):
        self.company.write(
            {"advance_customer_account_id": False, "advance_vendor_account_id": False}
        )
        self.env["res.config.settings"].create(
            {
                "advance_customer_account_id": self.customer_advances.id,
                "advance_vendor_account_id": self.vendor_prepayments.id,
            }
        ).execute()
        self.assertEqual(
            self.company.advance_customer_account_id, self.customer_advances
        )
        self.assertEqual(
            self.company.advance_vendor_account_id, self.vendor_prepayments
        )

    def test_posting_without_accounts_is_refused(self):
        self.company.advance_customer_account_id = False
        with self.assertRaises(UserError):
            self.advance(self.partner_a, 300)

    def test_invoicing_admin_sees_the_setting(self):
        # Invoicing only: without "full accounting features" core hides its
        # Default Accounts block
        admin = new_test_user(
            self.env,
            login="advance_invoicing_admin",
            groups="base.group_system,account.group_account_manager",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        self.assertFalse(admin.has_group("account.group_account_user"))
        Settings = self.env["res.config.settings"].with_user(admin)
        arch = Settings.get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertIn('name="advance_customer_account_id"', arch)

    def test_draft_saved_before_setup_posts_on_the_advance_account(self):
        self.company.advance_customer_account_id = False
        payment = self.env["account.payment"].create(
            {
                "is_advance": True,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 300,
                "journal_id": self.bank.id,
            }
        )
        self.company.advance_customer_account_id = self.customer_advances
        payment.action_post()
        self.assertEqual(payment.destination_account_id, self.customer_advances)
        self.assertEqual(payment.advance_residual, 300)

    def test_advance_needs_a_partner_and_the_right_direction(self):
        values = {
            "is_advance": True,
            "payment_type": "inbound",
            "partner_type": "customer",
            "amount": 50,
            "journal_id": self.bank.id,
        }
        Payment = self.env["account.payment"]
        with self.assertRaises(UserError):
            Payment.create(values).action_post()
        values["partner_id"] = self.partner_a.id
        # money paid to a customer, or received from a vendor, is no advance
        for wrong in ({"payment_type": "outbound"}, {"partner_type": "supplier"}):
            with self.assertRaises(UserError):
                Payment.create(dict(values, **wrong)).action_post()

    # ------------------------------------------------------------ registering

    def test_customer_advance_waits_on_its_own_account(self):
        payment = self.advance(self.partner_a, 300, user=self.billing)
        line = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.customer_advances
        )
        self.assertEqual(line.credit, 300)
        self.assertEqual(payment.advance_residual, 300)
        # the liability account must not turn it into a vendor payment
        self.assertEqual(payment.partner_type, "customer")
        self.assertEqual(payment.destination_account_id, self.customer_advances)
        # not an outstanding credit on the customer's receivable
        invoice = self.invoice("out_invoice", self.partner_a, 500)
        self.assertFalse(invoice.invoice_has_outstanding)
        self.assertTrue(invoice.has_open_advances)
        unapplied = self.env["account.payment"].search(
            [("is_advance", "=", True), ("advance_residual", ">", 0)]
        )
        self.assertEqual(unapplied, payment)

    def test_advance_flag_moves_the_counterpart_account(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 100,
                "journal_id": self.bank.id,
            }
        )
        self.assertEqual(
            payment.destination_account_id,
            self.partner_a.property_account_receivable_id,
        )
        payment.is_advance = True
        self.assertEqual(payment.destination_account_id, self.customer_advances)
        payment.action_post()
        self.assertIn(self.customer_advances, payment.move_id.line_ids.account_id)

    # ------------------------------------------------------------ applying

    def test_apply_to_invoice(self):
        payment = self.advance(self.partner_a, 300, user=self.billing)
        invoice = self.invoice("out_invoice", self.partner_a, 500)
        entry = self.apply(invoice, user=self.billing)
        self.assertEqual(invoice.amount_residual, 200)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertEqual(payment.advance_residual, 0)
        self.assertFalse(invoice.has_open_advances)
        self.assertEqual(entry.advance_payment_id, payment)
        self.assertEqual(entry.journal_id.type, "general")
        self.assertTrue(all(entry.line_ids.mapped("reconciled")))

    def test_advance_larger_than_invoice(self):
        payment = self.advance(self.partner_a, 300)
        first = self.invoice("out_invoice", self.partner_a, 200)
        self.apply(first)
        self.assertTrue(first.currency_id.is_zero(first.amount_residual))
        self.assertIn(first.payment_state, ("paid", "in_payment"))
        self.assertEqual(payment.advance_residual, 100)
        second = self.invoice("out_invoice", self.partner_a, 150)
        self.apply(second)
        self.assertEqual(second.amount_residual, 50)
        self.assertEqual(payment.advance_residual, 0)

    def test_vendor_prepayment_on_bill(self):
        payment = self.advance(self.partner_a, 300, kind="supplier")
        line = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.vendor_prepayments
        )
        self.assertEqual(line.debit, 300)
        bill = self.invoice("in_invoice", self.partner_a, 500)
        self.assertTrue(bill.has_open_advances)
        self.apply(bill)
        self.assertEqual(bill.amount_residual, 200)
        self.assertEqual(payment.advance_residual, 0)

    def test_customer_advance_not_offered_on_bill(self):
        self.advance(self.partner_a, 300)
        bill = self.invoice("in_invoice", self.partner_a, 500)
        self.assertFalse(bill.has_open_advances)

    def test_undo_gives_the_amount_back(self):
        payment = self.advance(self.partner_a, 300)
        invoice = self.invoice("out_invoice", self.partner_a, 500)
        entry = self.apply(invoice)
        entry.action_undo_advance()
        self.assertEqual(invoice.amount_residual, 500)
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertEqual(payment.advance_residual, 300)
        self.assertTrue(invoice.has_open_advances)
        self.assertTrue(entry.search_count([("reversed_entry_id", "=", entry.id)]))
        with self.assertRaises(UserError):
            self.invoice("out_invoice", self.partner_a, 1).action_undo_advance()

    def test_oldest_advance_is_proposed_first(self):
        old = self.advance(
            self.partner_a, 100, date=fields.Date.add(fields.Date.today(), days=-10)
        )
        self.advance(self.partner_a, 200)
        invoice = self.invoice("out_invoice", self.partner_a, 500)
        wizard = Form(
            self.env["account.advance.apply"].with_context(default_move_id=invoice.id)
        )
        self.assertEqual(wizard.payment_id, old)
        self.assertEqual(wizard.amount, 100)

    def test_contact_advance_counts_for_its_company(self):
        contact = self.env["res.partner"].create(
            {"name": "Buyer", "parent_id": self.partner_a.id}
        )
        payment = self.advance(contact, 300)
        invoice = self.invoice("out_invoice", self.partner_a, 500)
        self.apply(invoice, payment=payment)
        self.assertEqual(invoice.amount_residual, 200)

    def test_other_partner_advance_is_refused(self):
        other = self.advance(self.partner_b, 300)
        invoice = self.invoice("out_invoice", self.partner_a, 500)
        self.assertFalse(invoice.has_open_advances)
        wizard = self.env["account.advance.apply"].create(
            {"move_id": invoice.id, "payment_id": other.id, "amount": 100}
        )
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertEqual(other.advance_residual, 300)

    def test_amount_limits(self):
        payment = self.advance(self.partner_a, 300)
        invoice = self.invoice("out_invoice", self.partner_a, 200)
        for amount in (0, -5, 301, 250):  # zero, negative, above advance, above due
            wizard = self.env["account.advance.apply"].create(
                {"move_id": invoice.id, "payment_id": payment.id, "amount": amount}
            )
            with self.assertRaises(UserError):
                wizard.action_apply()
        self.assertEqual(payment.advance_residual, 300)

    def test_foreign_currency_invoice_is_refused(self):
        payment = self.advance(self.partner_a, 300)
        currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("id", "!=", self.company.currency_id.id)], limit=1)
        )
        currency.active = True
        invoice = self.invoice("out_invoice", self.partner_a, 500, currency=currency)
        self.assertFalse(invoice.has_open_advances)  # no Apply Advance button
        with self.assertRaises(UserError):
            invoice._apply_advance(payment, 100)
