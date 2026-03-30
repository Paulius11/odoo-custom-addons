{
    'name': 'Announcement Enhanced',
    'summary': 'Shows new in-session announcements as a dismissible header banner',
    'version': '17.0.1.0.0',
    'category': 'Web',
    'license': 'AGPL-3',
    'author': 'ELICS',
    'depends': ['announcement'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'announcement_enhanced/static/src/announcement_banner/announcement_banner.scss',
            'announcement_enhanced/static/src/announcement_banner/announcement_banner.xml',
            'announcement_enhanced/static/src/announcement_banner/announcement_banner.js',
        ],
    },
    'installable': True,
    'auto_install': False,
}
