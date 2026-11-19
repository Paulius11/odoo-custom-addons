{
    "name": "List Arrow Keys",
    "summary": "Arrow keys move between cells of an editable list, like a spreadsheet",
    "version": "17.0.1.0.1",
    "category": "Extra Tools",
    "website": "https://github.com/Paulius11/odoo-custom-addons",
    "author": "Paulius Gaizauskas",
    "maintainers": ["Paulius11"],
    "support": "paulius.gaizauskas@gmail.com",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "web_list_arrow_keys/static/src/list_renderer.js",
        ],
        "web.qunit_suite_tests": [
            "web_list_arrow_keys/static/tests/list_arrow_keys_tests.js",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
}
