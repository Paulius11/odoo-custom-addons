from odoo.tests import HttpCase, tagged

# Module import, not the names: a test class imported here would run the whole web suite
from odoo.addons.web.tests import test_js


@tagged("post_install", "-at_install")
class TestWebListArrowKeys(HttpCase):
    def test_qunit(self):
        """The QUnit tests in static/tests (needs Chrome; skipped without it)"""
        self.browser_js(
            "/web/tests?mod=web&filter=web_list_arrow_keys",
            "",
            "",
            login="admin",
            timeout=300,
            error_checker=test_js.qunit_error_checker,
        )
