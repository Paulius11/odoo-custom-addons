# -*- coding: utf-8 -*-
# Part of Simple Online Users. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, http
from odoo.exceptions import AccessError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

VISIBILITY_GROUPS = ('base.group_system', 'base.group_user')
STATUS_ORDER = {'online': 0, 'busy': 1, 'away': 2}

class OnlineUsersController(http.Controller):

    def _get_visibility_group(self):
        group = request.env['ir.config_parameter'].sudo().get_param('online_users.visibility_group')
        return group if group in VISIBILITY_GROUPS else 'base.group_system'

    def _check_access(self):
        # hiding the icon is not enough: portal users can call the routes directly
        if not request.env.user.has_group(self._get_visibility_group()):
            raise AccessError(_("You are not allowed to see the online users."))

    def _get_online_users_data(self):
        """Internal users as Discuss shows them; read only, the presence is Odoo's own"""
        me = request.env.user
        now = fields.Datetime.now()
        presences = request.env['mail.presence'].sudo().search([
            ('user_id.active', '=', True),
            ('user_id.share', '=', False),
            ('status', 'in', ('online', 'away')),
        ])
        presence_by_user = {presence.user_id.id: presence for presence in presences}

        users_data = []
        # the caller is looking at the screen, even before the websocket has reported in
        for user in presences.user_id | me.sudo():
            presence = presence_by_user.get(user.id)
            status = presence.status if presence else 'online'
            status = user.manual_im_status or status
            if status not in STATUS_ORDER:
                continue

            minutes = 0
            status_text = 'Active now'
            if status == 'busy':
                status_text = 'Do not disturb'
            elif status == 'away':
                if presence and presence.last_presence:
                    minutes = int((now - presence.last_presence).total_seconds() / 60)
                status_text = f'Away ({minutes}min)' if minutes else 'Away'

            users_data.append({
                'id': user.id,
                'name': user.name,
                'login': user.login,
                'status': status,
                'status_text': status_text,
                'away_minutes': minutes,
                'avatar_url': f'/web/image/res.users/{user.id}/avatar_128',
                'is_current_user': user.id == me.id,
            })
        return users_data

    @http.route('/online_users/get_count', type='jsonrpc', auth='user')
    def get_online_count(self):
        """Get count of currently online users using consistent logic"""
        self._check_access()
        try:
            # Use the same logic as get_online_users for consistency
            users_data = self._get_online_users_data()
            
            online_count = len(users_data)
            
            return {'count': online_count, 'success': True}
        except Exception as e:
            _logger.error("Error getting online users count: %s", e, exc_info=True)
            return {'count': 0, 'success': False, 'error': str(e)}

    @http.route('/online_users/get_visibility_group', type='jsonrpc', auth='user')
    def get_visibility_group(self):
        """Get the group that can see online users"""
        try:
            return {'group_xml_id': self._get_visibility_group(), 'success': True}
        except Exception as e:
            _logger.error("Error getting visibility group: %s", e)
            return {'group_xml_id': 'base.group_system', 'success': False}


    @http.route('/online_users/get_online_users', type='jsonrpc', auth='user')
    def get_online_users(self):
        """Get list of online users for the popup"""
        self._check_access()
        try:
            users_data = self._get_online_users_data()
            
            # Sort by status priority and then by last activity
            users_data.sort(key=lambda x: (STATUS_ORDER[x['status']], x['away_minutes']))
            
            return {'users': users_data, 'success': True}
        except Exception as e:
            _logger.error("Error getting online users list: %s", e, exc_info=True)
            return {'users': [], 'success': False, 'error': str(e)}