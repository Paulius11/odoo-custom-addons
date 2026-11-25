from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval

OPERATIONS = [
    ("read", "Read"),
    ("write", "Write"),
    ("create", "Create"),
    ("unlink", "Delete"),
]
MATCH = [("yes", "Yes"), ("no", "No")]


class SimpleAccessDebugger(models.TransientModel):
    _name = "simple.access.debugger"
    _description = "Access Debugger"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    model_id = fields.Many2one(
        "ir.model", domain=[("transient", "=", False)], ondelete="cascade"
    )
    operation = fields.Selection(OPERATIONS, required=True, default="read")
    res_id = fields.Integer(
        "Record ID", help="Optional: check one record instead of the whole model."
    )
    record_name = fields.Char("Record", compute="_compute_record_name")
    test_domain = fields.Text(
        "Domain to Try",
        help="A record rule domain, evaluated like a rule for the user: "
        "user, company_id, company_ids and time are available.",
    )
    verdict = fields.Text(readonly=True)
    verdict_state = fields.Selection(
        [("allowed", "Allowed"), ("blocked", "Blocked")], readonly=True
    )
    allowed_count = fields.Integer("Records Allowed", readonly=True)
    total_count = fields.Integer("Records in Total", readonly=True)
    test_domain_count = fields.Integer("Records Matching", readonly=True)
    test_domain_match = fields.Selection(MATCH, "Record Matches", readonly=True)
    acl_line_ids = fields.One2many(
        "simple.access.debugger.acl", "debugger_id", "Access Rights"
    )
    rule_line_ids = fields.One2many(
        "simple.access.debugger.rule", "debugger_id", "Record Rules"
    )
    model_line_ids = fields.One2many(
        "simple.access.debugger.model", "debugger_id", "All Models"
    )
    model_line_count = fields.Integer(compute="_compute_model_line_count")
    unreadable_model_count = fields.Integer(compute="_compute_model_line_count")

    @api.depends("user_id", "model_id")
    def _compute_display_name(self):
        for debugger in self:
            parts = [debugger.user_id.name, debugger.model_id.model]
            debugger.display_name = " · ".join(filter(None, parts)) or _("New")

    @api.depends("model_id", "res_id")
    def _compute_record_name(self):
        for debugger in self:
            name = False
            model = debugger.model_id.model
            if model in self.env and debugger.res_id:
                record = self.env[model].sudo().browse(debugger.res_id).exists()
                name = record.display_name if record else _("No such record")
            debugger.record_name = name

    @api.depends("model_line_ids.perm_read")
    def _compute_model_line_count(self):
        for debugger in self:
            lines = debugger.model_line_ids
            debugger.model_line_count = len(lines)
            debugger.unreadable_model_count = len(
                lines.filtered(lambda r: not r.perm_read)
            )

    @api.onchange("user_id", "model_id", "operation", "res_id")
    def _onchange_question(self):
        # an answer to the previous question would be misleading
        self.verdict = False
        self.verdict_state = False

    def _user_env(self):
        """The user's own rights, with all of their companies switched on."""
        return self.env(user=self.user_id.id, su=False, context={})

    def action_check(self):
        self.ensure_one()
        self.acl_line_ids.unlink()
        self.rule_line_ids.unlink()
        self.model_line_ids.unlink()
        values = {
            "verdict": False,
            "verdict_state": False,
            "allowed_count": 0,
            "total_count": 0,
            "test_domain_count": 0,
            "test_domain_match": False,
        }
        self._fill_model_lines()
        if self.model_id:
            if self.model_id.model not in self.env:
                raise UserError(_("The model %s is not loaded.", self.model_id.model))
            self._fill_acl_lines()
            self._fill_rule_lines()
            values.update(self._verdict())
            if self.test_domain:
                values.update(self._try_domain())
        self.write(values)

    def action_open_models(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Model Access of %s", self.user_id.name),
            "res_model": "simple.access.debugger.model",
            "view_mode": "tree",
            "domain": [("debugger_id", "=", self.id)],
            "context": {"create": False},
        }

    def _records(self):
        return self.env[self.model_id.model].sudo().with_context(active_test=False)

    def _record_matches(self, domain):
        records = self._records()
        found = records.search_count(
            expression.AND([[("id", "=", self.res_id)], domain])
        )
        return "yes" if found else "no"

    def _fill_model_lines(self):
        access = self._user_env()["ir.model.access"]
        lines = []
        for ir_model in self.env["ir.model"].search([("transient", "=", False)]):
            name = ir_model.model
            if name not in self.env or self.env[name]._abstract:
                continue
            line = {"debugger_id": self.id, "model_id": ir_model.id}
            for operation, _label in OPERATIONS:
                line[f"perm_{operation}"] = access.check(name, operation, False)
            lines.append(line)
        self.env["simple.access.debugger.model"].create(lines)

    def _fill_acl_lines(self):
        user_groups = self.user_id.groups_id
        perm = f"perm_{self.operation}"
        lines = []
        for access in self.env["ir.model.access"].search(
            [("model_id", "=", self.model_id.id)]
        ):
            in_group = not access.group_id or access.group_id in user_groups
            lines.append(
                {
                    "debugger_id": self.id,
                    "access_id": access.id,
                    "user_in_group": in_group,
                    "grants": in_group and access[perm],
                }
            )
        self.env["simple.access.debugger.acl"].create(lines)

    def _fill_rule_lines(self):
        user_groups = self.user_id.groups_id
        eval_context = self._user_env()["ir.rule"]._eval_context()
        lines = []
        for rule in self.env["ir.rule"].search(
            [("model_id", "=", self.model_id.id), (f"perm_{self.operation}", "=", True)]
        ):
            line = {
                "debugger_id": self.id,
                "rule_id": rule.id,
                "applies": not rule.groups or bool(rule.groups & user_groups),
            }
            try:
                # a broken domain may fail in SQL: keep the transaction usable
                with self.env.cr.savepoint():
                    domain = safe_eval(rule.domain_force or "[]", eval_context)
                    line["allowed_count"] = self._records().search_count(domain)
                    if self.res_id:
                        line["record_match"] = self._record_matches(domain)
            except Exception as error:  # noqa: BLE001 - showing it is the point
                line["error"] = str(error)
            lines.append(line)
        self.env["simple.access.debugger.rule"].create(lines)

    def _verdict(self):
        user_env = self._user_env()
        model = self.model_id.model
        operation = dict(OPERATIONS)[self.operation].lower()
        values = {"total_count": self._records().search_count([])}
        names = {"user": self.user_id.name, "op": operation, "model": model}
        if not user_env[model].check_access_rights(self.operation, False):
            groups = self.env["ir.model.access"].group_names_with_access(
                model, self.operation
            )
            text = _(
                "Blocked by access rights: no group of %(user)s may %(op)s %(model)s.",
                **names,
            )
            text += "\n" + (
                _("Groups that may: %s", ", ".join(groups))
                if groups
                else _("No group may do this.")
            )
            return dict(values, verdict=text, verdict_state="blocked")
        try:
            domain = user_env["ir.rule"]._compute_domain(model, self.operation)
        except Exception as error:  # noqa: BLE001 - showing it is the point
            text = _("A record rule cannot be evaluated: %s", error)
            return dict(values, verdict=text, verdict_state="blocked")
        values["allowed_count"] = self._records().search_count(domain)
        if not self.res_id:
            text = _(
                "%(user)s may %(op)s %(allowed)s of %(total)s %(model)s records.",
                allowed=values["allowed_count"],
                total=values["total_count"],
                **names,
            )
            state = "allowed" if values["allowed_count"] else "blocked"
            return dict(values, verdict=text, verdict_state=state)
        if not self._records().browse(self.res_id).exists():
            raise UserError(
                _("%(model)s has no record %(id)s.", model=model, id=self.res_id)
            )
        if self._record_matches(domain) == "yes":
            text = _("Allowed: %(user)s may %(op)s this record.", **names)
            return dict(values, verdict=text, verdict_state="allowed")
        record = user_env[model].browse(self.res_id)
        failing = user_env["ir.rule"]._get_failing(record, mode=self.operation)
        if failing:
            text = _(
                "Blocked by record rules: %s", ", ".join(failing.sudo().mapped("name"))
            )
        else:
            parents = ", ".join(self.env[model]._inherits)
            text = _("Blocked by the record rules of the parent model %s.", parents)
        return dict(values, verdict=text, verdict_state="blocked")

    def _try_domain(self):
        eval_context = self._user_env()["ir.rule"]._eval_context()
        try:
            with self.env.cr.savepoint():
                domain = safe_eval(self.test_domain, eval_context)
                values = {"test_domain_count": self._records().search_count(domain)}
                if self.res_id:
                    values["test_domain_match"] = self._record_matches(domain)
        except Exception as error:
            raise UserError(_("The domain to try fails: %s", error)) from error
        return values


class SimpleAccessDebuggerAcl(models.TransientModel):
    _name = "simple.access.debugger.acl"
    _description = "Access Debugger: Access Right"
    _order = "grants desc, user_in_group desc, id"

    debugger_id = fields.Many2one(
        "simple.access.debugger", required=True, ondelete="cascade"
    )
    access_id = fields.Many2one("ir.model.access", "Access Right", ondelete="cascade")
    group_id = fields.Many2one(related="access_id.group_id")
    perm_read = fields.Boolean(related="access_id.perm_read", string="Read")
    perm_write = fields.Boolean(related="access_id.perm_write", string="Write")
    perm_create = fields.Boolean(related="access_id.perm_create", string="Create")
    perm_unlink = fields.Boolean(related="access_id.perm_unlink", string="Delete")
    user_in_group = fields.Boolean("User Has Group")
    grants = fields.Boolean(help="This line gives the user the checked operation.")


class SimpleAccessDebuggerRule(models.TransientModel):
    _name = "simple.access.debugger.rule"
    _description = "Access Debugger: Record Rule"
    _order = "applies desc, id"

    debugger_id = fields.Many2one(
        "simple.access.debugger", required=True, ondelete="cascade"
    )
    rule_id = fields.Many2one("ir.rule", ondelete="cascade")
    is_global = fields.Boolean(related="rule_id.global", string="Global")
    groups = fields.Many2many(related="rule_id.groups")
    domain_force = fields.Text(related="rule_id.domain_force", string="Domain")
    applies = fields.Boolean(help="Global, or the user is in one of its groups.")
    allowed_count = fields.Integer(
        "Records Allowed", help="Records this rule's domain lets through."
    )
    record_match = fields.Selection(MATCH, "Record Passes")
    error = fields.Char()

    def action_try(self):
        self.ensure_one()
        self.debugger_id.test_domain = self.domain_force or "[]"


class SimpleAccessDebuggerModel(models.TransientModel):
    _name = "simple.access.debugger.model"
    _description = "Access Debugger: Model Access"
    _order = "model"

    debugger_id = fields.Many2one(
        "simple.access.debugger", required=True, ondelete="cascade"
    )
    model_id = fields.Many2one("ir.model", ondelete="cascade")
    model = fields.Char("Technical Name", related="model_id.model", store=True)
    perm_read = fields.Boolean("Read")
    perm_write = fields.Boolean("Write")
    perm_create = fields.Boolean("Create")
    perm_unlink = fields.Boolean("Delete")
