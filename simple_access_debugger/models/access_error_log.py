import logging
import time
import traceback

from odoo import api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

PARAM = "simple_access_debugger.log_access_errors"
REPEAT_AFTER = 600  # seconds before the same denial is reported again
_last_reported = {}


def _should_report(env, key):
    """Logging is on and this denial was not reported in the last 10 minutes.

    Odoo itself runs checks that fail and are caught quietly (the web app
    manifest does one on every page load of a non-admin user), so repeats
    would flood the log.
    """
    if not env["ir.config_parameter"].sudo().get_param(PARAM):
        return False
    # shortcut: kept per worker process, so each worker reports a denial once
    now = time.monotonic()
    key = (env.uid, *key)
    if now - _last_reported.get(key, -REPEAT_AFTER) < REPEAT_AFTER:
        return False
    _last_reported[key] = now
    return True


def _report(env, lines):
    user = env.user
    groups = ", ".join(sorted(user.sudo().groups_id.mapped("full_name")))
    stack = "".join(traceback.format_stack(limit=16)[:-2])
    lines += [
        f"User: {user.name} (id={user.id})",
        f"User groups: {groups}",
        "Called from:",
        stack,
    ]
    _logger.warning("\n".join(lines))


class IrModelAccess(models.Model):
    _inherit = "ir.model.access"

    @api.model
    def check(self, model, mode="read", raise_exception=True):
        try:
            return super().check(model, mode, raise_exception)
        except AccessError:
            if _should_report(self.env, ("acl", model, mode)):
                self._access_debugger_log(model, mode)
            raise

    def _access_debugger_log(self, model, mode):
        try:
            groups = self.group_names_with_access(model, mode)
            _report(
                self.env,
                [
                    f"Access denied by access rights: {mode} on {model}",
                    f"Groups that may {mode}: {', '.join(groups) or 'none'}",
                ],
            )
        except Exception:
            # never hide the real AccessError behind a failing report
            _logger.exception("Simple Access Debugger could not write its report")


class IrRule(models.Model):
    _inherit = "ir.rule"

    def _make_access_error(self, operation, records):
        error = super()._make_access_error(operation, records)
        key = ("rule", records._name, operation, tuple(records.ids[:20]))
        if _should_report(self.env, key):
            self._access_debugger_log(operation, records)
        return error

    def _access_debugger_log(self, operation, records):
        try:
            lines = [
                f"Access denied by record rules: {operation} on {records._name}",
                f"Records: {records.ids[:20]}",
                "Failing rules:",
            ]
            failing = self._get_failing(records, mode=operation).sudo()
            for rule in failing:
                scope = ", ".join(rule.groups.mapped("full_name")) or "global"
                lines.append(
                    f"- {rule.name} (id={rule.id}, {scope}): {rule.domain_force}"
                )
            if not failing:
                lines.append(
                    "- none on this model; check the rules of its parent models"
                )
            _report(self.env, lines)
        except Exception:
            # never hide the real AccessError behind a failing report
            _logger.exception("Simple Access Debugger could not write its report")
