import logging
from odoo import api, models, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def action_copy_permissions_wizard(self):
        """Open wizard to copy permissions from current user to selected user"""
        _logger.info(
            "User %s (ID: %s) initiated permission copy wizard",
            self.env.user.name,
            self.env.user.id
        )
        
        # Security check - only system administrators can access this
        if not self.env.user.has_group('base.group_system'):
            _logger.warning(
                "Unauthorized access attempt to permission copy wizard by user %s (ID: %s)",
                self.env.user.name,
                self.env.user.id
            )
            raise AccessError(_("Only system administrators can copy user permissions."))
        
        # Ensure we're working with a single record
        self.ensure_one()
        
        return {
            'name': _('Copy User Permissions'),
            'type': 'ir.actions.act_window',
            'res_model': 'user.permission.copy.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_user_id': self.id,
                'active_model': self._name,
                'active_id': self.id,
            }
        }

    @api.model
    def _get_copyable_permission_fields(self):
        """Define which permission-related fields should be copied"""
        # Get all fields of the user model
        user_fields = self.fields_get()
        
        # Base fields that we always want to copy if they exist
        base_fields = [
            'groups_id',           # User groups (main permissions)
            'company_ids',         # Multi-company access
            'company_id',          # Default company
        ]
        
        # Optional fields that might exist in some Odoo versions/configurations
        optional_fields = [
            'category_id',         # User category (might not exist in all versions)
            'sel_groups_1_2_3',    # Selection groups
            'sel_groups_4_5_6',
            'sel_groups_7_8_9',
            'sel_groups_10_11_12',
        ]
        
        # Only include fields that actually exist in the model
        copyable_fields = []
        for field in base_fields + optional_fields:
            if field in user_fields:
                copyable_fields.append(field)
                
        _logger.debug(
            "Copyable permission fields found: %s",
            ', '.join(copyable_fields)
        )
        
        return copyable_fields

    def _prepare_field_value_for_copy(self, field_name, field_value):
        """
        Prepare field value for copying based on field type
        
        Args:
            field_name (str): Name of the field
            field_value: Value of the field
            
        Returns:
            Prepared value for write operation
        """
        field_info = self.fields_get([field_name]).get(field_name, {})
        field_type = field_info.get('type')
        
        try:
            if field_type == 'many2many':
                # For Many2many fields, use Command.set()
                return [(6, 0, field_value.ids if field_value else [])]
            elif field_type == 'many2one':
                # For Many2one fields
                return field_value.id if field_value else False
            elif field_type == 'selection':
                # For selection fields, return the value directly
                return field_value
            else:
                # For other field types, return the value directly
                return field_value
        except Exception as e:
            _logger.warning(
                "Failed to prepare value for field %s: %s. Skipping this field.",
                field_name, str(e)
            )
            return None

    def copy_permissions_to_user(self, target_user_id):
        """
        Copy all permissions from current user to target user
        
        Args:
            target_user_id (int): ID of the target user
            
        Returns:
            dict: Action result or success message
        """
        self.ensure_one()
        
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only system administrators can copy user permissions."))
        
        target_user = self.env['res.users'].browse(target_user_id)
        if not target_user.exists():
            raise UserError(_("Target user not found."))
        
        # Prevent copying to admin user
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin_user and target_user.id == admin_user.id:
            raise UserError(_("Cannot modify the administrator user permissions."))
        
        # Prevent copying to current user (self-copy)
        if target_user.id == self.id:
            raise UserError(_("Cannot copy permissions to the same user."))
        
        _logger.info(
            "Starting permission copy from user %s (ID: %s) to user %s (ID: %s)",
            self.name, self.id, target_user.name, target_user.id
        )
        
        try:
            # Get copyable fields
            copyable_fields = self._get_copyable_permission_fields()
            
            if not copyable_fields:
                raise UserError(_("No copyable permission fields found."))
            
            # Prepare values to copy
            values_to_copy = {}
            copied_fields = []
            skipped_fields = []
            
            for field_name in copyable_fields:
                try:
                    field_value = getattr(self, field_name)
                    prepared_value = self._prepare_field_value_for_copy(field_name, field_value)
                    
                    if prepared_value is not None:
                        values_to_copy[field_name] = prepared_value
                        copied_fields.append(field_name)
                    else:
                        skipped_fields.append(field_name)
                        
                except Exception as e:
                    _logger.warning(
                        "Error processing field %s: %s. Skipping this field.",
                        field_name, str(e)
                    )
                    skipped_fields.append(field_name)
            
            if not values_to_copy:
                raise UserError(_("No valid permission fields found to copy."))
            
            _logger.info(
                "Copying fields: %s. Skipping fields: %s",
                ', '.join(copied_fields),
                ', '.join(skipped_fields) if skipped_fields else 'none'
            )
            
            # Update target user with copied permissions
            target_user.write(values_to_copy)
            
            _logger.info(
                "Successfully copied permissions from user %s (ID: %s) to user %s (ID: %s). "
                "Copied fields: %s",
                self.name, self.id, target_user.name, target_user.id,
                ', '.join(copied_fields)
            )
            
            # Prepare success message
            success_details = []
            if 'groups_id' in copied_fields:
                group_count = len(self.groups_id)
                success_details.append(_("%d security groups") % group_count)
            if 'company_ids' in copied_fields:
                company_count = len(self.company_ids)
                success_details.append(_("%d company access rights") % company_count)
            if 'company_id' in copied_fields and self.company_id:
                success_details.append(_("default company: %s") % self.company_id.name)
                
            details_text = ', '.join(success_details) if success_details else _("basic permissions")
            
            # Fixed message formatting - using string formatting instead of keyword arguments
            success_message = _('Permissions successfully copied from %s to %s.\nCopied: %s') % (
                self.name, target_user.name, details_text
            )
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': success_message,
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(
                "Failed to copy permissions from user %s (ID: %s) to user %s (ID: %s). Error: %s",
                self.name, self.id, target_user.name, target_user.id, error_msg
            )
            
            # Provide more user-friendly error messages
            if 'category_id' in error_msg:
                raise UserError(_(
                    "Failed to copy user category. This field might not be available in your Odoo configuration. "
                    "Other permissions have been copied successfully."
                ))
            elif 'company_id' in error_msg:
                raise UserError(_("Failed to copy company settings. Please check company access rights. Error: %s") % error_msg)
            elif 'groups_id' in error_msg:
                raise UserError(_("Failed to copy security groups. Please check group permissions. Error: %s") % error_msg)
            else:
                raise UserError(_("Failed to copy permissions: %s") % error_msg)