{
    'name': 'Simple Online Users',
    'version': '19.0.1.0.1',
    'category': 'Website/Tools',
    'author': 'Paulius Gaizauskas',
    'website': 'https://github.com/Paulius11/odoo-custom-addons',
    'summary': 'Display online users count in systray',
    'depends': ['base', 'web', 'bus', 'mail'],  # 19.0: presence moved to mail.presence
    'data': [
        'data/config_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'simple_online_users/static/src/js/online_users.js',
            'simple_online_users/static/src/xml/online_users.xml',
        ],
    },
    'images': ['static/description/banner.png', 'static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'support': 'paulius.gaizauskas@gmail.com',
}