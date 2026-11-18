import io
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
import xlsxwriter
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date, format_datetime, formatLang
from odoo.tools.safe_eval import datetime as safe_datetime
from odoo.tools.safe_eval import dateutil as safe_dateutil
from odoo.tools.safe_eval import safe_eval
from odoo.tools.safe_eval import time as safe_time

_logger = logging.getLogger(__name__)

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SCHEDULE_FIELDS = {
    "active",
    "frequency",
    "month_day",
    "send_hour",
    "user_id",
    *WEEKDAYS,
}
NUMERIC_TYPES = ("integer", "float", "monetary")
# The mail body shows at most this many rows; the Excel file always has all of them.
BODY_ROW_LIMIT = 500


class SimpleScheduledReport(models.Model):
    _name = "simple.scheduled.report"
    _description = "Scheduled Report"
    _inherit = "mail.thread"
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    user_id = fields.Many2one(
        "res.users",
        string="Owner",
        required=True,
        default=lambda self: self.env.user,
        ondelete="cascade",
        tracking=True,
        help="The report reads the records as this user: it lists only what the owner "
        "may see.",
    )
    model_id = fields.Many2one(
        "ir.model",
        required=True,
        ondelete="cascade",
        domain=[("transient", "=", False)],
    )
    model_name = fields.Char(string="Technical Model Name", related="model_id.model")
    domain = fields.Char(string="Filter", default="[]")
    date_field_id = fields.Many2one(
        "ir.model.fields",
        ondelete="set null",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('date', 'datetime')),"
        " ('store', '=', True)]",
        help="Keep only the records whose date falls in the period.",
    )
    period = fields.Selection(
        [("last", "Last"), ("this", "This")], default="last", required=True
    )
    period_count = fields.Integer(default=1)
    period_unit = fields.Selection(
        [("day", "Days"), ("week", "Weeks"), ("month", "Months")],
        default="day",
        required=True,
    )
    column_ids = fields.One2many(
        "simple.scheduled.report.column", "report_id", copy=True
    )
    groupby_field_id = fields.Many2one(
        "ir.model.fields",
        string="Group By",
        ondelete="set null",
        domain="[('model_id', '=', model_id), ('ttype', 'in',"
        " ('many2one', 'selection', 'char', 'boolean', 'date', 'integer'))]",
    )
    frequency = fields.Selection(
        [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")],
        default="weekly",
        required=True,
    )
    mon = fields.Boolean(string="Monday", default=True)
    tue = fields.Boolean(string="Tuesday")
    wed = fields.Boolean(string="Wednesday")
    thu = fields.Boolean(string="Thursday")
    fri = fields.Boolean(string="Friday")
    sat = fields.Boolean(string="Saturday")
    sun = fields.Boolean(string="Sunday")
    month_day = fields.Integer(
        string="Day of Month",
        default=1,
        help="31 sends on the last day of every month.",
    )
    send_hour = fields.Float(
        string="Send At", default=7.0, help="In the owner's timezone."
    )
    next_send = fields.Datetime(readonly=True, copy=False)
    last_sent = fields.Datetime(readonly=True, copy=False)
    recipient_user_ids = fields.Many2many("res.users", string="Users")
    recipient_partner_ids = fields.Many2many("res.partner", string="Contacts")
    email_to = fields.Char(string="Other Emails", help="Addresses separated by commas.")
    attach_xlsx = fields.Boolean(string="Attach Excel File", default=True)
    skip_empty = fields.Boolean(
        string="Skip If Empty", help="Send nothing when no record matches."
    )

    @api.constrains("period_count", "month_day", "send_hour", "frequency", *WEEKDAYS)
    def _check_schedule(self):
        for report in self:
            if report.period_count < 1:
                raise ValidationError(_("The period must count at least 1."))
            if not 1 <= report.month_day <= 31:
                raise ValidationError(
                    _("The day of the month must be between 1 and 31.")
                )
            if not 0 <= report.send_hour < 24:
                raise ValidationError(
                    _("The send time must be between 00:00 and 23:59.")
                )
            if report.frequency == "weekly" and not any(
                report[day] for day in WEEKDAYS
            ):
                raise ValidationError(_("Pick at least one weekday."))

    @api.constrains("model_id", "column_ids", "date_field_id", "groupby_field_id")
    def _check_fields_model(self):
        for report in self:
            used = (
                report.column_ids.field_id
                | report.date_field_id
                | report.groupby_field_id
            )
            if used.model_id - report.model_id:
                raise ValidationError(
                    _("Every field must belong to the report's model.")
                )

    @api.onchange("model_id")
    def _onchange_model_id(self):
        self.column_ids = [fields.Command.clear()]
        self.date_field_id = self.groupby_field_id = False

    @api.model_create_multi
    def create(self, vals_list):
        reports = super().create(vals_list)
        reports._schedule_next()
        return reports

    def write(self, vals):
        res = super().write(vals)
        if SCHEDULE_FIELDS & set(vals):
            self._schedule_next()
        return res

    # Schedule

    def _schedule_next(self, after=None):
        after = after or fields.Datetime.now()
        for report in self:
            report.next_send = report.active and report._next_send_after(after)

    def _is_send_day(self, day):
        if self.frequency == "weekly":
            return self[WEEKDAYS[day.weekday()]]
        if self.frequency == "monthly":
            last_day = (day + relativedelta(day=31)).day
            return day.day == min(self.month_day, last_day)
        return True

    def _next_send_after(self, after):
        """The first send time after `after` (naive UTC), as naive UTC."""
        self.ensure_one()
        tz = pytz.timezone(self.user_id.tz or "UTC")
        local_after = pytz.utc.localize(after).astimezone(tz)
        hours, minutes = divmod(round(self.send_hour * 60), 60)
        day = local_after.date()
        for _offset in range(400):
            if self._is_send_day(day):
                local = tz.localize(datetime.combine(day, time(hours, minutes)))
                if local > local_after:
                    return local.astimezone(pytz.utc).replace(tzinfo=None)
            day += timedelta(days=1)
        return False

    @api.model
    def _cron_send_due(self):
        now = fields.Datetime.now()
        for report in self.search([("next_send", "<=", now)]):
            try:
                with self.env.cr.savepoint():
                    report._send_report()
            except Exception as error:  # one broken report must not stop the others
                _logger.exception("Scheduled report %s could not be sent", report.id)
                report.message_post(body=_("The report could not be sent: %s", error))
            report._schedule_next(now)

    # Send

    def action_send_now(self):
        sent = self.filtered(lambda report: report._send_report())
        if sent:
            message, kind = _("The report was sent."), "success"
        else:
            message, kind = _("No record matches, so nothing was sent."), "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": message,
                "type": kind,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    def _send_report(self):
        """Mail the report now. Returns the mail, or False when it was skipped."""
        self.ensure_one()
        data = self._collect()
        if not data["count"] and self.skip_empty:
            return False
        owner = self.user_id
        body = (
            self.env["ir.qweb"]
            .with_context(lang=owner.lang)
            ._render("simple_scheduled_reports.report_mail_body", data)
        )
        attachments = self.env["ir.attachment"]
        if self.attach_xlsx:
            attachments = attachments.create(
                {
                    "name": f"{self.name}.xlsx",
                    "raw": self._render_xlsx(data),
                    "res_model": self._name,
                    "res_id": self.id,
                    "mimetype": "application/vnd.openxmlformats-officedocument"
                    ".spreadsheetml.sheet",
                }
            )
        partners = self.recipient_partner_ids | self.recipient_user_ids.partner_id
        mail = (
            self.env["mail.mail"]
            .sudo()
            .create(
                {
                    "subject": data["subject"],
                    "body_html": body,
                    "email_from": owner.email_formatted
                    or self.env.company.email_formatted,
                    "recipient_ids": [fields.Command.set(partners.ids)],
                    "email_to": self.email_to,
                    "attachment_ids": [fields.Command.set(attachments.ids)],
                }
            )
        )
        recipients = partners.mapped("display_name") + [self.email_to or ""]
        self.message_post(
            body=_(
                "Sent %(count)s rows to %(recipients)s.",
                count=data["count"],
                recipients=", ".join(filter(None, recipients)) or _("nobody"),
            ),
            attachment_ids=attachments.ids,
        )
        self.last_sent = fields.Datetime.now()
        self.env.ref("mail.ir_cron_mail_scheduler_action")._trigger()
        return mail

    # Data

    def _owner_env(self):
        owner = self.user_id
        return (
            self.with_user(owner)
            .with_context(
                lang=owner.lang, tz=owner.tz, allowed_company_ids=owner.company_ids.ids
            )
            .env
        )

    def _period(self, today):
        """(first day, day after the last) of the report period."""
        unit = self.period_unit
        if unit == "week":
            start = today - timedelta(days=today.weekday())
        elif unit == "month":
            start = today.replace(day=1)
        else:
            start = today
        step = relativedelta(**{f"{unit}s": 1})
        if self.period == "this":
            return start, start + step
        return start - step * self.period_count, start

    def _search_domain(self, env, today):
        owner = env.user
        domain = safe_eval(
            self.domain or "[]",
            {
                "uid": owner.id,
                "user": owner,
                "datetime": safe_datetime,
                "dateutil": safe_dateutil,
                "time": safe_time,
                "relativedelta": relativedelta,
                "context_today": lambda: today,
            },
        )
        if not self.date_field_id:
            return domain, ""
        start, end = self._period(today)
        name = self.date_field_id.name
        if self.date_field_id.ttype == "datetime":
            tz = pytz.timezone(owner.tz or "UTC")
            low, high = (
                tz.localize(datetime.combine(day, time.min))
                .astimezone(pytz.utc)
                .replace(tzinfo=None)
                for day in (start, end)
            )
        else:
            low, high = start, end
        period = (
            f"{format_date(env, start)} – {format_date(env, end - timedelta(days=1))}"
        )
        return domain + [(name, ">=", low), (name, "<", high)], period

    def _cell(self, field, record):
        """(text for the mail, value for Excel) of one field of one record."""
        value = record[field.name]
        env = record.env
        if field.type in ("many2one", "many2many", "reference"):
            text = ", ".join(value.mapped("display_name")) if value else ""
            return text, text
        if field.type == "selection":
            text = dict(field._description_selection(env)).get(value, "")
            return text, text
        if field.type == "boolean":
            return (_("Yes") if value else _("No")), bool(value)
        if field.type in NUMERIC_TYPES:
            currency = (
                field.type == "monetary" and record[field.get_currency_field(record)]
            )
            return self._number(env, field, value, currency), value
        if not value:
            return "", ""
        if field.type == "date":
            return format_date(env, value), value
        if field.type == "datetime":
            local = fields.Datetime.context_timestamp(record, value).replace(
                tzinfo=None
            )
            return format_datetime(env, value, tz=env.user.tz), local
        return str(value), str(value)

    def _number(self, env, field, value, currency=None):
        if currency:
            return formatLang(env, value, currency_obj=currency)
        if field.type == "integer":
            return formatLang(env, value, digits=0)
        digits = field.get_digits(env) if field.type == "float" else None
        return formatLang(env, value, digits=digits[1] if digits else 2)

    def _totals(self, env, fields_, records, rows):
        totals = []
        for index, field in enumerate(fields_):
            if field.type not in NUMERIC_TYPES or field.group_operator != "sum":
                totals.append(("", ""))
                continue
            total = sum(row[index][1] for row in rows)
            currency = None
            if field.type == "monetary":
                currencies = records.mapped(field.get_currency_field(records))
                currency = currencies if len(currencies) == 1 else None
            totals.append((self._number(env, field, total, currency), total))
        return totals

    def _collect(self):
        """Read the records as the owner: all the mail and the Excel file show."""
        self.ensure_one()
        env = self._owner_env()
        model = env[self.model_name]
        today = fields.Date.context_today(model)
        domain, period = self._search_domain(env, today)
        # shortcut: no row cap on the search, so a report over millions of rows is
        # slow; add a limit field if one shows up.
        records = model.search(domain)
        fields_ = [
            model._fields[column.field_id.name] for column in self.column_ids
        ] or [model._fields["display_name"]]
        group_field = (
            self.groupby_field_id and model._fields[self.groupby_field_id.name]
        )
        by_key = defaultdict(lambda: model.browse())
        for record in records:
            key = (
                self._cell(group_field, record)[0] or _("None") if group_field else None
            )
            by_key[key] |= record
        has_totals = any(
            f.type in NUMERIC_TYPES and f.group_operator == "sum" for f in fields_
        )
        groups, all_rows, shown = [], [], 0
        for key in sorted(by_key, key=lambda k: k or ""):
            group_records = by_key[key]
            rows = [
                [self._cell(f, record) for f in fields_] for record in group_records
            ]
            all_rows += rows
            groups.append(
                {
                    "label": key,
                    "count": len(rows),
                    "rows": rows,
                    "body_rows": rows[: max(BODY_ROW_LIMIT - shown, 0)],
                    "totals": has_totals
                    and self._totals(env, fields_, group_records, rows),
                }
            )
            shown += len(groups[-1]["body_rows"])
        return {
            "report": self,
            "subject": f"{self.name} ({format_date(env, today)})",
            "period": period,
            "headers": [f._description_string(env) for f in fields_],
            "groups": groups,
            "grouped": bool(group_field),
            "count": len(records),
            "hidden": len(records) - shown,
            "has_totals": has_totals,
            "grand_totals": has_totals
            and self._totals(env, fields_, records, all_rows),
        }

    def _render_xlsx(self, data):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet()
        bold = workbook.add_format({"bold": True})
        group_style = workbook.add_format({"bold": True, "bg_color": "#f3ecf1"})
        styles = {
            datetime: workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"}),
            type(fields.Date.today()): workbook.add_format(
                {"num_format": "yyyy-mm-dd"}
            ),
            float: workbook.add_format({"num_format": "#,##0.00"}),
        }
        sheet.write_row(0, 0, data["headers"], bold)
        sheet.set_column(0, len(data["headers"]) - 1, 24)
        sheet.freeze_panes(1, 0)
        row = 1

        def write_cells(cells, style=None):
            for col, (_text, value) in enumerate(cells):
                sheet.write(row, col, value, styles.get(type(value), style))

        for group in data["groups"]:
            if data["grouped"]:
                sheet.write(row, 0, f"{group['label']} ({group['count']})", group_style)
                row += 1
            for cells in group["rows"]:
                write_cells(cells)
                row += 1
            if data["grouped"] and group["totals"]:
                write_cells(group["totals"], bold)
                row += 1
        if data["grand_totals"]:
            write_cells(data["grand_totals"], bold)
            if data["grand_totals"][0][0] == "":
                sheet.write(row, 0, _("Total"), bold)
        workbook.close()
        return output.getvalue()
