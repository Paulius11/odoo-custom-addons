{
    'name': 'User Message',
    'summary': 'Send a direct OdooBot message to a user from their profile',
    'version': '17.0.1.1.1',
    'category': 'Technical',
    'license': 'AGPL-3',
    'author': 'Paulius Gaižauskas',
    'website': 'https://www.elicsengineering.com',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/user_message_wizard_views.xml',
        'views/res_users_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'auto_install': False,
}
