import hashlib
import logging
import re
import threading
from collections import ChainMap, Counter

from odoo import SUPERUSER_ID, _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError
from odoo.modules.registry import Registry
from odoo.tools import SQL
from odoo.tools.translate import CodeTranslations

_logger = logging.getLogger(__name__)

# {dbname: (sequence of the registry's "default" cache, {lang: {source: value}})}:
# live code-term overrides of each database, laid over every module's .po. An Apply
# in any worker clears that cache, which moves the sequence in every worker.
_LAYERS = {}


def _code_layer(lang):
    """Live code-term overrides of the database this thread serves, or None."""
    dbname = getattr(threading.current_thread(), "dbname", None)
    registry = Registry.registries.get(dbname) if dbname else None
    if (
        not registry
        or not registry.ready
        or "translation.override" not in registry.models
    ):
        return None
    sequence = registry.cache_sequences.get("default")
    entry = _LAYERS.get(dbname)
    if entry is None or entry[0] != sequence:
        layer = {}
        try:
            with registry.cursor() as cr:
                cr.execute(
                    "SELECT lang, source, value FROM translation_override "
                    "WHERE kind = 'code' AND value IS NOT NULL AND value != ''"
                )
                for row_lang, source, value in cr.fetchall():
                    layer.setdefault(row_lang, {})[source] = value
        except Exception:
            _logger.exception("custom_translate: cannot load code-term changes")
            return None
        entry = _LAYERS[dbname] = (sequence, layer)
    return entry[1].get(lang)


_super_get_python_translations = CodeTranslations.get_python_translations


def get_python_translations(self, module_name, lang):
    translations = _super_get_python_translations(self, module_name, lang)
    layer = _code_layer(lang)
    return ChainMap(layer, translations) if layer else translations


CodeTranslations.get_python_translations = get_python_translations

PLACEHOLDER_RE = re.compile(r"%(?:\([^)]*\))?[-#0+]*\d*(?:\.\d+)?[sdifrxX]|\{[^{}]*\}")
TAG_RE = re.compile(r"<[^>]*>")
PROTECTED = {"value", "original_value", "original_missing", "original_taken"}
IMMUTABLE = {
    "key",
    "lang",
    "kind",
    "source",
    "location",
    "res_model",
    "res_field",
    "res_id",
}


def check_translation(source, value):
    """Refuse a translation that would break a format call or inject markup."""
    if not (value or "").strip():
        raise UserError(_("The translation cannot be empty."))
    for pattern, what in (
        (PLACEHOLDER_RE, _("placeholders")),
        (TAG_RE, _("HTML tags")),
    ):
        expected = pattern.findall(source or "")
        if Counter(expected) != Counter(pattern.findall(value)):
            raise UserError(
                _(
                    "The translation must keep exactly the same %(what)s as the "
                    "English text: %(items)s",
                    what=what,
                    items=", ".join(expected) or _("none"),
                )
            )


def make_key(kind, source, res_model=False, res_field=False, res_id=0):
    raw = "\x1f".join(
        [kind, res_model or "", res_field or "", str(res_id or 0), source]
    )
    return hashlib.sha1(raw.encode()).hexdigest()


class TranslationOverride(models.Model):
    """One changed term in one language: its draft, live value and original."""

    _name = "translation.override"
    _description = "Translation Change"
    _order = "write_date desc, id desc"
    _rec_name = "source"

    key = fields.Char(required=True, index=True, readonly=True)
    lang = fields.Selection(
        selection="_get_languages", string="Language", required=True, readonly=True
    )
    kind = fields.Selection(
        [("code", "Code term"), ("db", "Database term")],
        required=True,
        readonly=True,
    )
    source = fields.Text("English", required=True, readonly=True)
    location = fields.Char(readonly=True)
    res_model = fields.Char(readonly=True)
    res_field = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    value = fields.Text(
        "Live translation",
        readonly=True,
        help="What users see now. Empty: Odoo's own translation is shown.",
    )
    pending_value = fields.Text("Draft", help="Not visible to users until applied.")
    pending_uid = fields.Many2one("res.users", "Draft by", readonly=True)
    state = fields.Selection(
        [("pending", "Draft"), ("live", "Live"), ("original", "Original")],
        compute="_compute_state",
        store=True,
    )
    original_value = fields.Text(
        "Odoo translation",
        readonly=True,
        help="The translation before the first change; Revert restores it.",
    )
    original_missing = fields.Boolean(readonly=True)
    original_taken = fields.Boolean(readonly=True)
    change_ids = fields.One2many("translation.change", "override_id", readonly=True)

    _sql_constraints = [  # noqa: RUF012 - Odoo's own declaration
        ("key_lang_uniq", "unique(key, lang)", "This term already has a change."),
    ]

    @api.model
    def _get_languages(self):
        return self.env["res.lang"].get_installed()

    @api.depends("value", "pending_value")
    def _compute_state(self):
        for rec in self:
            if rec.pending_value:
                rec.state = "pending"
            elif rec.value:
                rec.state = "live"
            else:
                rec.state = "original"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("lang") == "en_US":
                raise UserError(
                    _(
                        "English is the source language: "
                        "switch your language to translate."
                    )
                )
            # original_value on create is informative only: the DB snapshot that
            # Revert uses is taken at first apply (original_taken)
            self._check_protected(vals, PROTECTED - {"original_value"})
            if vals.get("pending_value"):
                check_translation(vals.get("source"), vals["pending_value"])
                vals.setdefault("pending_uid", self.env.uid)
        return super().create(vals_list)

    def write(self, vals):
        self._check_protected(vals, PROTECTED | IMMUTABLE)
        if vals.get("pending_value"):
            for rec in self:
                check_translation(rec.source, vals["pending_value"])
            vals.setdefault("pending_uid", self.env.uid)
        return super().write(vals)

    def _check_protected(self, vals, names):
        """Live and original values change only through Apply and Revert."""
        if not self.env.su and names & set(vals):
            raise AccessError(
                _("Only Apply and Revert can change: %s", ", ".join(names & set(vals)))
            )

    # ------------------------------------------------------------------
    # Apply and revert
    # ------------------------------------------------------------------

    def action_apply_pending(self):
        pending = self.search([("state", "=", "pending")])
        if not pending:
            return self._notify(_("Nothing to apply: there are no drafts."), "info")
        changes = [(rec, rec.value, rec.pending_value) for rec in pending]
        for rec, _old, new in changes:
            rec.sudo().write(
                {"value": new, "pending_value": False, "pending_uid": False}
            )
        pending._push_live()
        self.env["translation.change.set"]._log(
            "apply", changes, _("Applied: %s", pending._summary())
        )
        return self._notify(
            _("%s change(s) are live. Reload the page to see them.", len(changes)),
            "success",
            reload=True,
        )

    def action_discard_draft(self):
        self.write({"pending_value": False, "pending_uid": False})
        return True

    def action_revert(self):
        """Back to Odoo's own translation, for these terms only."""
        live = self.filtered("value")
        self.action_discard_draft()
        if not live:
            return self._notify(_("These terms already show Odoo's translation."))
        changes = [(rec, rec.value, False) for rec in live]
        live.sudo().write({"value": False})
        live._push_live()
        self.env["translation.change.set"]._log(
            "revert_term", changes, _("Reverted: %s", live._summary())
        )
        return self._notify(
            _("%s term(s) reverted. Reload the page to see them.", len(live)),
            "success",
            reload=True,
        )

    def action_revert_all(self):
        """Every term back to what it was before this addon touched it."""
        everything = self.search([])
        live = everything.filtered("value")
        everything.action_discard_draft()
        if not live:
            return self._notify(_("Nothing to revert: no term is changed."))
        changes = [(rec, rec.value, False) for rec in live]
        live.sudo().write({"value": False})
        live._push_live()
        self.env["translation.change.set"]._log(
            "revert_all", changes, _("Reverted everything: %s", live._summary())
        )
        return self._notify(
            _("All %s changed term(s) are back to Odoo's translation.", len(live)),
            "success",
            reload=True,
        )

    def _summary(self):
        """Short label of these terms for the history: 'Phone, Sales (+3 more)'."""
        names = [(rec.source or "").strip()[:30] for rec in self[:3]]
        more = len(self) - len(names)
        return ", ".join(names) + (_(" (+%s more)", more) if more else "")

    @api.model
    def _notify(self, message, kind="info", reload=False):
        params = {"message": message, "type": kind, "sticky": False}
        if reload:
            params["next"] = {"type": "ir.actions.client", "tag": "reload"}
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }

    def _push_live(self):
        """Make the stored ``value`` (or the original, when empty) what Odoo shows."""
        for rec in self.filtered(lambda r: r.kind == "db"):
            rec._write_db()
        if any(rec.kind == "code" for rec in self):
            self._sync_code_layer()
        self.env.registry.clear_cache("default", "templates")

    # ------------------------------------------------------------------
    # Code terms
    # ------------------------------------------------------------------

    @api.model
    def _sync_code_layer(self):
        # reloaded on the next lookup; other workers follow the cache sequence
        self.flush_model(["kind", "lang", "source", "value"])
        _LAYERS.pop(self.env.cr.dbname, None)

    @api.model
    @tools.ormcache("lang")
    def _live_code_terms(self, lang):
        rows = self.sudo().search_read(
            [("kind", "=", "code"), ("lang", "=", lang), ("value", "!=", False)],
            ["source", "value"],
        )
        return {row["source"]: row["value"] for row in rows}

    # ------------------------------------------------------------------
    # Database terms
    # ------------------------------------------------------------------

    def _target(self):
        self.ensure_one()
        if self.res_model not in self.env:
            return None, None
        record = self.env[self.res_model].with_user(SUPERUSER_ID).browse(self.res_id)
        field = record._fields.get(self.res_field)
        if not record.exists() or not field or not field.translate:
            return None, None
        return record, field

    def _read_db(self, record, field):
        """Return (value, missing) of this term in self.lang, as stored now."""
        if callable(field.translate):
            translations, _ctx = record.get_field_translations(field.name, [self.lang])
            entry = next((t for t in translations if t["source"] == self.source), None)
            if entry is None:
                return None, True
            return entry["value"] or False, not entry["value"]
        self.env.flush_all()
        self.env.cr.execute(
            SQL(
                "SELECT %s->>%s FROM %s WHERE id = %s",
                SQL.identifier(field.name),
                self.lang,
                SQL.identifier(record._table),
                record.id,
            )
        )
        raw = self.env.cr.fetchone()[0]
        return raw, raw is None

    def _write_db(self):
        record, field = self._target()
        if record is None:
            _logger.warning(
                "custom_translate: %s %s,%s no longer exists, skipped",
                self.location,
                self.res_model,
                self.res_id,
            )
            return False
        current, missing = self._read_db(record, field)
        if callable(field.translate) and current is None:
            _logger.warning(
                "custom_translate: term %r is no longer in %s, skipped",
                self.source,
                self.location,
            )
            return False
        if not self.original_taken:
            self.sudo().write(
                {
                    "original_taken": True,
                    "original_value": current or False,
                    "original_missing": missing,
                }
            )
        if self.value:
            target, target_missing = self.value, False
        elif self.original_taken:
            target, target_missing = self.original_value, self.original_missing
        else:
            return False
        if (current or False) == (target or False) and missing == target_missing:
            return False
        if callable(field.translate):
            old_term = current or self.source
            try:
                record.update_field_translations(
                    field.name, {self.lang: {old_term: target or self.source}}
                )
            except Exception as e:
                raise UserError(
                    _(
                        "Could not change %(where)s: %(error)s",
                        where=self.location,
                        error=e,
                    )
                ) from e
        else:
            # direct jsonb write: the ORM path re-runs setup_models per field label
            self.env.cr.execute(
                SQL(
                    "UPDATE %(table)s SET %(col)s = CASE WHEN %(missing)s "
                    "THEN %(col)s - %(lang)s ELSE COALESCE(%(col)s, '{}'::jsonb) "
                    "|| jsonb_build_object(%(lang)s, %(value)s::text) END "
                    "WHERE id = %(id)s",
                    table=SQL.identifier(record._table),
                    col=SQL.identifier(field.name),
                    missing=target_missing,
                    lang=self.lang,
                    value=target or "",
                    id=record.id,
                )
            )
            record.invalidate_recordset([field.name])
        return True

    @api.model
    def _reapply_db(self):
        """Put live DB terms back after a module upgrade or a language reload."""
        changed = 0
        for rec in self.sudo().search([("kind", "=", "db"), ("value", "!=", False)]):
            try:
                with self.env.cr.savepoint():
                    changed += bool(rec._write_db())
            except Exception:
                _logger.exception(
                    "custom_translate: could not re-apply %s", rec.location
                )
        if changed:
            _logger.info("custom_translate: re-applied %s database term(s)", changed)
            self.env.registry.clear_cache("default", "templates")
        return changed

    def _register_hook(self):
        super()._register_hook()
        _LAYERS.pop(self.env.cr.dbname, None)
        self._reapply_db()

    @api.model
    def _restore_all_originals(self):
        """Uninstall hook: give every DB term back its original translation."""
        for rec in self.sudo().search(
            [("kind", "=", "db"), ("original_taken", "=", True)]
        ):
            rec.sudo().value = False
            try:
                with self.env.cr.savepoint():
                    rec._write_db()
            except Exception:
                _logger.exception(
                    "custom_translate: could not restore %s", rec.location
                )
        _LAYERS.pop(self.env.cr.dbname, None)
