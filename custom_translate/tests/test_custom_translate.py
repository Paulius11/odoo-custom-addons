import threading

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.translate import code_translations

from ..models import translation_override
from ..models.translation_override import make_key

LANG = "lt_LT"
PY_SOURCE = "At least one language must be active."  # base, odoo-python


@tagged("post_install", "-at_install")
class TestCustomTranslate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the code layer reloads through registry.cursor(), as in another request:
        # in test mode that cursor sees this test's uncommitted changes
        cls.registry.enter_test_mode(cls.cr)
        cls.addClassCleanup(cls.registry.leave_test_mode)
        cls.env["res.lang"]._activate_lang(LANG)
        cls.Term = cls.env["translation.term"]
        cls.Override = cls.env["translation.override"]

    def setUp(self):
        super().setUp()
        # the layer may hold this test's rolled-back changes: reload it afterwards
        self.addCleanup(translation_override._LAYERS.clear)

    def _term(
        self, kind, source, value=False, res_model=False, res_field=False, res_id=0
    ):
        return self.Term.create(
            {
                "lang": LANG,
                "kind": kind,
                "key": make_key(kind, source, res_model, res_field, res_id),
                "source": source,
                "value": value,
                "location": "test",
                "res_model": res_model,
                "res_field": res_field,
                "res_id": res_id,
            }
        )

    def _apply(self, term, value):
        term.save_draft(value)
        self.assertEqual(term.override_id.state, "pending")
        self.Override.action_apply_pending()
        return term.override_id

    def _menu(self, name, lt=None):
        menu = self.env["ir.ui.menu"].create({"name": name})
        if lt:
            menu.update_field_translations("name", {LANG: lt})
        return menu

    def _menu_lt(self, menu):
        menu.invalidate_recordset()
        return menu.with_context(lang=LANG).name

    def test_code_term_python_and_webclient(self):
        original = code_translations.get_python_translations("base", LANG)[PY_SOURCE]
        term = self._term("code", PY_SOURCE, original)
        term.save_draft("Bent viena kalba turi likti aktyvi.")
        self.assertEqual(
            code_translations.get_python_translations("base", LANG)[PY_SOURCE],
            original,
            "a draft is not live",
        )
        self.Override.action_apply_pending()
        self.assertEqual(
            code_translations.get_python_translations("base", LANG)[PY_SOURCE],
            "Bent viena kalba turi likti aktyvi.",
        )
        translations, _params = self.env["ir.http"].get_translations_for_webclient(
            None, LANG
        )
        self.assertEqual(list(translations)[-1], "custom_translate_overrides")
        self.assertIn(
            {"id": PY_SOURCE, "string": "Bent viena kalba turi likti aktyvi."},
            translations["custom_translate_overrides"]["messages"],
        )
        term.action_revert()
        self.assertEqual(
            code_translations.get_python_translations("base", LANG)[PY_SOURCE], original
        )
        translations, _params = self.env["ir.http"].get_translations_for_webclient(
            None, LANG
        )
        overrides = translations.get("custom_translate_overrides", {"messages": []})
        self.assertNotIn(PY_SOURCE, [m["id"] for m in overrides["messages"]])

    def test_db_menu_apply_reapply_revert(self):
        menu = self._menu("CT Menu", "Senas meniu")
        term = self._term("db", "CT Menu", "Senas meniu", "ir.ui.menu", "name", menu.id)
        override = self._apply(term, "Naujas meniu")
        self.assertEqual(self._menu_lt(menu), "Naujas meniu")
        self.assertEqual(override.original_value, "Senas meniu")
        # a module upgrade or a language reload puts Odoo's translation back
        menu.update_field_translations("name", {LANG: "Senas meniu"})
        self.assertEqual(self.Override._reapply_db(), 1)
        self.assertEqual(self._menu_lt(menu), "Naujas meniu")
        term.action_revert()
        self.assertEqual(self._menu_lt(menu), "Senas meniu")
        self.assertEqual(override.state, "original")

    def test_db_missing_original_is_restored_as_missing(self):
        menu = self._menu("CT Untranslated")
        term = self._term("db", "CT Untranslated", False, "ir.ui.menu", "name", menu.id)
        self._apply(term, "Išverstas")
        self.assertEqual(self._menu_lt(menu), "Išverstas")
        term.action_revert()
        self.env.cr.execute(
            "SELECT name ? %s FROM ir_ui_menu WHERE id = %s", [LANG, menu.id]
        )
        self.assertFalse(self.env.cr.fetchone()[0])

    def test_view_term(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "ct.test",
                "model": "res.partner",
                "type": "form",
                "arch": "<form><div>Hello World</div></form>",
            }
        )
        view.update_field_translations(
            "arch_db", {LANG: {"Hello World": "Labas pasauli"}}
        )
        term = self._term(
            "db", "Hello World", "Labas pasauli", "ir.ui.view", "arch_db", view.id
        )
        self._apply(term, "Sveikas pasauli")
        view.invalidate_recordset()
        self.assertIn("Sveikas pasauli", view.with_context(lang=LANG).arch_db)
        term.action_revert()
        view.invalidate_recordset()
        self.assertIn("Labas pasauli", view.with_context(lang=LANG).arch_db)

    def test_change_set_revert(self):
        menu = self._menu("CT Sets", "Pradinis")
        term = self._term("db", "CT Sets", "Pradinis", "ir.ui.menu", "name", menu.id)
        Sets = self.env["translation.change.set"]
        self._apply(term, "Pirmas")
        first = Sets.search([], limit=1)
        self._apply(term, "Antras")
        second = Sets.search([], limit=1)
        # the first set's term was changed again later: left alone
        first.action_revert()
        self.assertEqual(self._menu_lt(menu), "Antras")
        second.action_revert()
        self.assertEqual(self._menu_lt(menu), "Pirmas")
        self.assertTrue(second.reverted_by_id)
        with self.assertRaises(UserError):
            second.action_revert()

    def test_revert_all(self):
        menu = self._menu("CT All", "Pradinis")
        db_term = self._term("db", "CT All", "Pradinis", "ir.ui.menu", "name", menu.id)
        code_term = self._term("code", PY_SOURCE, "x")
        db_term.save_draft("Pakeistas")
        code_term.save_draft("Pakeistas kodas")
        self.Override.action_apply_pending()
        other = self._menu("CT Draft only", "Juodraštis")
        self._term(
            "db", "CT Draft only", "Juodraštis", "ir.ui.menu", "name", other.id
        ).save_draft("x")
        self.Override.action_revert_all()
        self.assertEqual(self._menu_lt(menu), "Pradinis")
        self.assertNotEqual(
            code_translations.get_python_translations("base", LANG)[PY_SOURCE],
            "Pakeistas kodas",
        )
        self.assertFalse(self.Override.search([("state", "!=", "original")]))
        self.assertEqual(
            self.env["translation.change.set"].search([], limit=1).operation,
            "revert_all",
        )

    def test_validation_and_access(self):
        term = self._term("code", "Hello %s, you have %(count)s items")
        with self.assertRaises(UserError):
            term.save_draft("Labas, turite elementų")
        term.save_draft("Labas %s, turite %(count)s elementų")
        markup = self._term("code", "Plain text")
        with self.assertRaises(UserError):
            markup.save_draft('Tekstas <img src=x onerror="alert(1)">')
        user = new_test_user(
            self.env,
            "ct_translator",
            groups="base.group_user,custom_translate.group_translator",
        )
        override = term.override_id.with_user(user)
        override.write({"pending_value": "Sveiki %s, turite %(count)s"})
        with self.assertRaises(AccessError):
            override.write({"value": "<b>live</b>"})
        with self.assertRaises(UserError):
            self.Override.create(
                {"key": "k", "lang": "en_US", "kind": "code", "source": "s"}
            )

    def test_find_terms(self):
        self._term("code", "Find me please", "Surask mane")
        self.env["ir.config_parameter"].set_param(
            f"custom_translate.terms.{LANG}", self.Term._modules_fingerprint()
        )
        found = self.Term.find_terms("Surask mane", LANG)
        self.assertEqual([f["source"] for f in found], ["Find me please"])
        self.assertTrue(found[0]["suggested"])

    def test_flow_as_translator(self):
        user = new_test_user(
            self.env,
            "ct_flow",
            groups="base.group_user,custom_translate.group_translator",
        )
        menu = self._menu("CT Flow", "Pradinis")
        term = self._term("db", "CT Flow", "Pradinis", "ir.ui.menu", "name", menu.id)
        code_term = self._term("code", PY_SOURCE, "x")
        (term | code_term).with_user(user).save_draft("Vertėjo tekstas")
        self.Override.with_user(user).action_apply_pending()
        self.assertEqual(self._menu_lt(menu), "Vertėjo tekstas")
        change_set = self.env["translation.change.set"].search([], limit=1)
        self.assertEqual(change_set.user_id, user)
        change_set.with_user(user).action_revert()
        self.assertEqual(self._menu_lt(menu), "Pradinis")
        self.Override.with_user(user).action_revert_all()

    def test_code_layer_other_worker_and_database(self):
        term = self._term("code", PY_SOURCE, "x")
        self._apply(term, "Kito darbuotojo tekstas")
        db = self.env.cr.dbname
        sequences = self.registry.cache_sequences
        sequence = sequences.get("default")
        self.addCleanup(sequences.__setitem__, "default", sequence)
        # another worker still holds the layer it loaded before the Apply
        translation_override._LAYERS[db] = (sequence, {})
        self.assertNotEqual(
            code_translations.get_python_translations("base", LANG)[PY_SOURCE],
            "Kito darbuotojo tekstas",
        )
        # its next request sees the cleared cache (check_signaling moves the sequence)
        sequences["default"] = (sequence or 0) + 1
        self.assertEqual(
            code_translations.get_python_translations("base", LANG)[PY_SOURCE],
            "Kito darbuotojo tekstas",
        )
        # a thread serving another database never sees this database's change
        thread = threading.current_thread()
        self.addCleanup(setattr, thread, "dbname", thread.dbname)
        thread.dbname = "custom_translate_other_db"
        self.assertNotEqual(
            code_translations.get_python_translations("base", LANG)[PY_SOURCE],
            "Kito darbuotojo tekstas",
        )

    def test_translator_cannot_forge(self):
        user = new_test_user(
            self.env,
            "ct_forger",
            groups="base.group_user,custom_translate.group_translator",
        )
        menu = self._menu("CT Forge", "Pradinis")
        term = self._term("db", "CT Forge", "Pradinis", "ir.ui.menu", "name", menu.id)
        # a term may only get a translation, not a new target
        with self.assertRaises(AccessError):
            term.with_user(user).write({"res_model": "ir.ui.view", "res_id": 1})
        term.with_user(user).write({"new_value": "Vertimas"})
        self.assertEqual(term.override_id.pending_value, "Vertimas")
        # changes and history come from Apply and Revert only
        with self.assertRaises(AccessError):
            self.Override.with_user(user).create(
                {
                    "key": "forged",
                    "lang": LANG,
                    "kind": "db",
                    "source": "CT Forge",
                    "res_model": "ir.ui.menu",
                    "res_field": "name",
                    "res_id": menu.id,
                }
            )
        with self.assertRaises(AccessError):
            self.env["translation.change.set"].with_user(user).create(
                {"name": "forged", "operation": "apply"}
            )
        with self.assertRaises(AccessError):
            term.override_id.with_user(user).write({"location": "elsewhere"})
        # the raw-SQL rebuild is for translators only
        plain = new_test_user(self.env, "ct_plain", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.Term.with_user(plain).refresh_terms(LANG)

    def test_english_has_no_term_list(self):
        english = [("lang", "=", "en_US")]
        before = self.Term.search_count(english)
        for lang in ("en_US", "xx_XX", None):  # an inactive language means English
            Term = self.Term.with_context(lang=lang)
            self.assertEqual(Term.action_open_terms()["tag"], "display_notification")
            self.assertEqual(Term.action_refresh()["tag"], "display_notification")
        self.assertEqual(self.Term.find_terms("Phone", "en_US"), [])
        self.assertEqual(self.Term.search_count(english), before, "no index built")

    def test_term_list_rebuilt_when_modules_change(self):
        self.Term.refresh_terms(LANG)
        self.assertFalse(self.Term._is_stale(LANG))
        self.assertTrue(
            self.Term.search_count([("lang", "=", LANG), ("kind", "=", "code")])
        )
        # what an install or upgrade does to the fingerprint
        self.env["ir.config_parameter"].set_param(
            f"custom_translate.terms.{LANG}", "old"
        )
        self.assertTrue(self.Term._is_stale(LANG))
        self.Term.find_terms("Naujas", LANG)
        self.assertFalse(self.Term._is_stale(LANG))
