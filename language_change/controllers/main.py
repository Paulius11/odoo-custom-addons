# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class LanguageSwitcherController(http.Controller):
    
    @http.route('/language_switcher/switch_language', type='json', auth='user')
    def switch_language(self, lang_code):
        """Switch the user's language preference and return success status"""
        if not lang_code:
            _logger.warning("No language code provided in language switch request")
            return {'error': 'No language code provided'}
        
        try:
            # Check if the language exists
            lang = request.env['res.lang'].sudo().search([
                ('code', '=', lang_code), 
                ('active', '=', True)
            ], limit=1)
            
            if not lang:
                _logger.warning("User %s attempted to switch to non-existent language: %s", 
                               request.env.user.login, lang_code)
                return {'error': 'Language not found or not active'}
            
            # Set language preference for the user
            request.env.user.write({'lang': lang_code})
            request.env.context = dict(request.env.context, lang=lang_code)
            
            _logger.info("User %s switched language to %s", 
                        request.env.user.login, lang_code)
            return {'success': True, 'lang': lang_code}
            
        except Exception as e:
            _logger.exception("Error switching language to %s: %s", 
                             lang_code, str(e))
            return {'error': str(e)}