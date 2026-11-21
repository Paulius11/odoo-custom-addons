from odoo import api, models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def get_translations_for_webclient(self, modules, lang):
        translations, lang_params = super().get_translations_for_webclient(
            modules, lang
        )
        terms = self.env["translation.override"]._live_code_terms(
            lang or self._context.get("lang")
        )
        if terms:
            # the browser merges modules in key order, so the last key wins
            translations = dict(translations)
            translations["custom_translate_overrides"] = {
                "messages": [{"id": src, "string": val} for src, val in terms.items()]
            }
        return translations, lang_params
