import json

from odoo.tests import HttpCase, new_test_user, tagged

PASSWORD = "language-change-test"


@tagged("post_install", "-at_install")
class TestLanguageChange(HttpCase):
    def test_switch_language(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        user = new_test_user(self.env, login="lang_switcher", password=PASSWORD)
        self.authenticate(user.login, PASSWORD)
        response = self.url_open(
            "/language_switcher/switch_language",
            data=json.dumps({"jsonrpc": "2.0", "params": {"lang_code": "fr_FR"}}),
            headers={"Content-Type": "application/json"},
        ).json()
        self.assertEqual(response["result"], {"success": True, "lang": "fr_FR"})
        user.invalidate_recordset()
        self.assertEqual(user.lang, "fr_FR")
