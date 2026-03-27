{
    'name': 'User Message',
    'summary': 'Send a direct OdooBot message to a user from their profile',
    'description': '''
        Allows administrators to send a personalized message to any user.
        The message is delivered as a direct chat message from OdooBot,
        appearing in the user's Discuss inbox.
    ''',
    'version': '17.0.1.1.0',
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
    'installable': True,
    'auto_install': False,
}
