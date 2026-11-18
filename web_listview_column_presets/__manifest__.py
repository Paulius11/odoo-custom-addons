{
    "name": "List View Column Presets",
    "summary": "Save the columns of a list view as presets, switch back in one click",
    "version": "17.0.2.3.0",
    "category": "Extra Tools",
    "website": "https://github.com/Paulius11/odoo-custom-addons",
    "author": "Paulius Gaizauskas",
    "maintainers": ["Paulius11"],
    "support": "paulius.gaizauskas@gmail.com",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "security/ir.model.access.csv",
        "security/security.xml",
        "views/ir_listview_column_preset_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "web_listview_column_presets/static/src/js/column_preset_service.js",
            "web_listview_column_presets/static/src/js/save_preset_dialog.js",
            "web_listview_column_presets/static/src/js/save_preset_dialog.xml",
            "web_listview_column_presets/static/src/xml/list_renderer_template.xml",
            "web_listview_column_presets/static/src/js/list_renderer_patch.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
}
