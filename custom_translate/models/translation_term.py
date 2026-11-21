import hashlib
import logging
import re

from psycopg2.extras import execute_values

from odoo import _, _lt, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import CodeTranslations

from .translation_override import make_key

_logger = logging.getLogger(__name__)

# backend view types only; QWeb (reports, website, mail) is left out on purpose
VIEW_TYPES = (
    "form",
    "tree",
    "kanban",
    "search",
    "calendar",
    "pivot",
    "graph",
    "activity",
)
# plain-text DB terms: (model, field, location label)
TEXT_FIELDS = [
    ("ir.ui.menu", "name", _lt("Menu")),
    ("ir.model.fields", "field_description", _lt("Field label")),
    ("ir.model.fields.selection", "name", _lt("Selection value")),
    ("ir.actions.act_window", "name", _lt("Action")),
]
COLUMNS = (
    "lang",
    "kind",
    "key",
    "source",
    "value",
    "translated",
    "location",
    "module",
    "res_model",
    "res_field",
    "res_id",
)
NO_WORDS_RE = re.compile(r"^[\W\d_]*$")


class TranslationTerm(models.Model):
    """Searchable index of every translatable UI term, rebuilt per language."""

    _name = "translation.term"
    _description = "Translatable Term"
    _order = "source, location"
    _rec_name = "source"
    _log_access = False

    lang = fields.Char(required=True, index=True, readonly=True)
    kind = fields.Selection(
        [("code", "Code term"), ("db", "Database term")], readonly=True
    )
    key = fields.Char(index=True, readonly=True)
    source = fields.Text("English", readonly=True)
    value = fields.Text("Odoo translation", readonly=True)
    translated = fields.Boolean(readonly=True)
    location = fields.Char(readonly=True)
    module = fields.Char("Modules", readonly=True)
    res_model = fields.Char(readonly=True)
    res_field = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    override_id = fields.Many2one("translation.override", readonly=True, index=True)
    state = fields.Selection(related="override_id.state", string="Status")
    live_value = fields.Text(related="override_id.value", string="Live translation")
    new_value = fields.Text(
        "Your translation",
        compute="_compute_new_value",
        inverse="_inverse_new_value",
        readonly=False,
        help="Saved as a draft; Apply makes drafts live.",
    )

    @api.depends("override_id.pending_value")
    def _compute_new_value(self):
        for term in self:
            term.new_value = term.override_id.pending_value

    def _inverse_new_value(self):
        for term in self:
            if term.new_value:
                term.save_draft(term.new_value)
            elif term.override_id.pending_value:
                term.override_id.action_discard_draft()

    # ------------------------------------------------------------------
    # Drafts
    # ------------------------------------------------------------------

    def write(self, vals):
        # the index comes from the database; Apply writes where a term points
        if not self.env.su and set(vals) - {"new_value"}:
            raise AccessError(_("Only your translation can be changed on a term."))
        return super().write(vals)

    def _ensure_override(self):
        Override = self.env["translation.override"]
        result = Override
        for term in self:
            override = term.override_id or Override.search(
                [("key", "=", term.key), ("lang", "=", term.lang)], limit=1
            )
            if not override:
                # sudo: a change is only ever made from an indexed term
                override = (
                    Override.sudo()
                    .create(
                        {
                            "key": term.key,
                            "lang": term.lang,
                            "kind": term.kind,
                            "source": term.source,
                            "location": term.location,
                            "res_model": term.res_model,
                            "res_field": term.res_field,
                            "res_id": term.res_id,
                            # code: the .po value; db: snapshot again at first apply
                            "original_value": term.value or False,
                        }
                    )
                    .sudo(False)
                )
            self.sudo().search(
                [("key", "=", term.key), ("lang", "=", term.lang)]
            ).override_id = override
            result |= override
        return result

    def save_draft(self, value):
        """Store ``value`` as the draft of these terms (called from the live popup)."""
        overrides = self._ensure_override()
        overrides.write({"pending_value": value})
        return {
            "pending": self.env["translation.override"].search_count(
                [("state", "=", "pending")]
            )
        }

    def action_revert(self):
        return self.override_id.action_revert()

    def action_apply_pending(self):
        return self.env["translation.override"].action_apply_pending()

    @api.model
    def _ui_lang(self):
        """The language to translate into; None (an inactive one) shows English."""
        return self.env.lang or "en_US"

    @api.model
    def _english_notice(self):
        # nothing to translate into: no 28,000-row index nobody can edit
        return self.env["translation.override"]._notify(
            _(
                "Your language is English, the source language. Switch your "
                "language in your preferences to the one you want to translate into."
            ),
            "warning",
        )

    @api.model
    def action_open_terms(self):
        lang = self._ui_lang()
        if lang == "en_US":
            return self._english_notice()
        if self._is_stale(lang):
            self.refresh_terms(lang)
        return {
            "type": "ir.actions.act_window",
            "name": _("Terms (%s)", lang),
            "res_model": "translation.term",
            "view_mode": "tree",
            "domain": [("lang", "=", lang)],
            "help": _("<p>No terms: click Refresh term list.</p>"),
        }

    # ------------------------------------------------------------------
    # Live mode lookup
    # ------------------------------------------------------------------

    @api.model
    def find_terms(self, text, lang, model=False, hint=None):
        """Terms whose English text or current translation is exactly ``text``.

        ``hint`` comes from where the user clicked: ``menu_id`` (a navbar item)
        or ``area`` ("menu", "label"); it decides which matches are pre-ticked.
        """
        text = (text or "").strip()
        if not text or len(text) > 2000 or not lang or lang == "en_US":
            return []
        if self._is_stale(lang):
            self.refresh_terms(lang)
        terms = self.search(
            [
                ("lang", "=", lang),
                "|",
                "|",
                ("value", "=", text),
                ("source", "=", text),
                ("override_id.value", "=", text),
            ],
            limit=60,
        )
        hint = hint or {}

        def suggested(t):
            if hint.get("menu_id"):
                return t.res_model == "ir.ui.menu" and t.res_id == hint["menu_id"]
            if hint.get("area") == "menu":
                return t.res_model == "ir.ui.menu"
            mentions_model = bool(model) and (
                f"[{model}]" in (t.location or "")
                or f": {model}." in (t.location or "")
            )
            if hint.get("area") == "label":
                return mentions_model
            return t.kind == "code" or mentions_model

        flags = {t.id: suggested(t) for t in terms}
        terms = terms.sorted(lambda t: (not flags[t.id], t.kind != "code", t.location))
        return [
            {
                "id": t.id,
                "kind": t.kind,
                "location": t.location,
                "source": t.source,
                "value": t.value,
                "live": t.live_value or False,
                "pending": t.override_id.pending_value or False,
                "suggested": flags[t.id],
            }
            for t in terms
        ]

    @api.model
    def get_pending_count(self):
        return self.env["translation.override"].search_count(
            [("state", "=", "pending")]
        )

    # ------------------------------------------------------------------
    # Index rebuild
    # ------------------------------------------------------------------

    def action_refresh(self):
        lang = self._ui_lang()
        if lang == "en_US":
            return self._english_notice()
        count = self.refresh_terms(lang)
        return self.env["translation.override"]._notify(
            _("%(count)s terms found for %(lang)s.", count=count, lang=lang),
            "success",
            reload=True,
        )

    @api.model
    def _modules_fingerprint(self):
        """Changes whenever a module is installed, removed or upgraded."""
        self.env.cr.execute(
            "SELECT name, latest_version FROM ir_module_module "
            "WHERE state = 'installed' ORDER BY name"
        )
        return hashlib.sha1(repr(self.env.cr.fetchall()).encode()).hexdigest()

    @api.model
    def _is_stale(self, lang):
        """No terms yet, or built before the last module install/upgrade."""
        built = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(f"custom_translate.terms.{lang}")
        )
        return built != self._modules_fingerprint() or not self.search_count(
            [("lang", "=", lang)], limit=1
        )

    @api.model
    def refresh_terms(self, lang):
        # raw SQL below skips the ACL; translators only
        self.check_access_rights("write")
        rows = self._collect_code_terms(lang) + self._collect_db_terms(lang)
        cr = self.env.cr
        self.env.flush_all()
        cr.execute("DELETE FROM translation_term WHERE lang = %s", [lang])
        execute_values(
            cr._obj,
            f"INSERT INTO translation_term ({', '.join(COLUMNS)}) VALUES %s",
            [tuple(row[c] for c in COLUMNS) for row in rows],
            page_size=2000,
        )
        cr.execute(
            """UPDATE translation_term t SET override_id = o.id
                 FROM translation_override o
                WHERE o.key = t.key AND o.lang = t.lang AND t.lang = %s""",
            [lang],
        )
        # a DB term that is live shows its own value in the database: show the original
        cr.execute(
            """UPDATE translation_term t
                  SET value = COALESCE(o.original_value, t.source),
                      translated = o.original_value IS NOT NULL
                 FROM translation_override o
                WHERE o.id = t.override_id AND o.kind = 'db'
                  AND o.original_taken AND t.lang = %s""",
            [lang],
        )
        self.invalidate_model()
        self.env["ir.config_parameter"].sudo().set_param(
            f"custom_translate.terms.{lang}", self._modules_fingerprint()
        )
        _logger.info("custom_translate: indexed %s terms for %s", len(rows), lang)
        return len(rows)

    @api.model
    def _row(
        self,
        lang,
        kind,
        source,
        value,
        location,
        module=False,
        res_model=False,
        res_field=False,
        res_id=0,
    ):
        return {
            "lang": lang,
            "kind": kind,
            "key": make_key(kind, source, res_model, res_field, res_id),
            "source": source,
            "value": value or None,
            "translated": bool(value) and value != source,
            "location": location,
            "module": module or None,
            "res_model": res_model or None,
            "res_field": res_field or None,
            "res_id": res_id or None,
        }

    @api.model
    def _collect_code_terms(self, lang):
        modules = self.env["ir.module.module"].search([("state", "=", "installed")])
        merged = {}  # source -> [value, modules]
        for module in modules.mapped("name"):
            try:
                terms = CodeTranslations._get_code_translations(
                    module, lang, lambda row: True
                )
            except (OSError, ValueError):
                _logger.debug("custom_translate: no .po for %s/%s", module, lang)
                continue
            for source, value in terms.items():
                if not source or NO_WORDS_RE.match(source):
                    continue
                entry = merged.setdefault(source, [value, []])
                entry[0] = entry[0] or value
                entry[1].append(module)
        return [
            self._row(
                lang,
                "code",
                source,
                value,
                _("Code"),
                module=", ".join(mods[:5]) + (" …" if len(mods) > 5 else ""),
            )
            for source, (value, mods) in merged.items()
        ]

    @api.model
    def _collect_db_terms(self, lang):
        rows = []
        cr = self.env.cr
        labels = dict(
            self.env["ir.model"].sudo().search([]).mapped(lambda m: (m.model, m.name))
        )
        cr.execute(
            "SELECT id, parent_id, COALESCE(name->>%s, name->>'en_US') FROM ir_ui_menu",
            [lang],
        )
        menus = {mid: (parent, name) for mid, parent, name in cr.fetchall()}

        def menu_path(menu_id, depth=0):
            parent, name = menus.get(menu_id, (None, "?"))
            if parent and depth < 10:
                return f"{menu_path(parent, depth + 1)} / {name}"
            return name

        for model, field, label in TEXT_FIELDS:
            table = self.env[model]._table
            extra = {
                "ir.model.fields": "t.model || '.' || t.name",
                "ir.model.fields.selection": (
                    "(SELECT f.model || '.' || f.name FROM ir_model_fields f"
                    " WHERE f.id = t.field_id) || ' = ' || t.value"
                ),
            }.get(model, "NULL")
            cr.execute(
                f"""SELECT t.id, t.{field}->>'en_US', t.{field}->>%s, {extra}
                      FROM {table} t WHERE t.{field}->>'en_US' IS NOT NULL""",
                [lang],
            )
            for res_id, source, value, detail in cr.fetchall():
                if not source or NO_WORDS_RE.match(source):
                    continue
                if model == "ir.ui.menu":
                    detail = menu_path(res_id)
                where = f"{label}: {detail}" if detail else str(label)
                rows.append(
                    self._row(
                        lang, "db", source, value, where, False, model, field, res_id
                    )
                )
        View = self.env["ir.ui.view"].sudo()
        view_label = _("View")
        arch_field = View._fields["arch_db"]
        cr.execute(
            """SELECT id, name, model, arch_db->>'en_US', arch_db->>%s
                 FROM ir_ui_view WHERE active AND type IN %s
                  AND arch_db IS NOT NULL""",
            [lang, VIEW_TYPES],
        )
        for res_id, name, model, arch_en, arch_lang in cr.fetchall():
            if not arch_en:
                continue
            try:
                terms = arch_field.get_translation_dictionary(
                    arch_en, {lang: arch_lang or arch_en}
                )
            except Exception:  # noqa: BLE001 - one unparsable view must not stop the index
                _logger.debug("custom_translate: cannot parse view %s", res_id)
                continue
            where = f"{view_label}: {labels.get(model, model or '')} ({name}) [{model}]"
            for source, by_lang in terms.items():
                if NO_WORDS_RE.match(source):
                    continue
                value = by_lang.get(lang)
                rows.append(
                    self._row(
                        lang,
                        "db",
                        source,
                        value if value != source else False,
                        where,
                        False,
                        "ir.ui.view",
                        "arch_db",
                        res_id,
                    )
                )
        return rows
