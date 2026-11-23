{
    "name": "POS Network Printer",
    "summary": "Receipts and kitchen tickets on ESC/POS network printers, no IoT box",
    "version": "19.0.1.0.1",
    "category": "Sales/Point of Sale",
    "website": "https://github.com/Paulius11/odoo-custom-addons",
    "author": "Paulius Gaizauskas",
    "maintainers": ["Paulius11"],
    "support": "paulius.gaizauskas@gmail.com",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [
        "views/pos_printer_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_escpos_printer/static/src/app/**/*",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
}
