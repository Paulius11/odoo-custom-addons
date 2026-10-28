{
    'name': 'Module Version',
    'version': '17.0.4.9.1',
    'category': 'Extra Tools',
    'summary': 'Display module version, track lifecycle history, and check for App Store updates',
    'author': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
    'support': 'paulius.gaizauskas@gmail.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/module_upgrade_history_views.xml',
        'views/ir_module_module_views.xml',
        'views/ir_module_update_info_views.xml',
        'views/res_config_settings_view.xml',
        'views/ir_cron_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'module_version/static/src/css/styles.css',
        ],
    },
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
