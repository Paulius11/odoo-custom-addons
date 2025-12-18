import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class UserPermissionCopyWizard(models.TransientModel):
    _name = 'user.permission.copy.wizard'
    _description = 'User Permission Copy Wizard'

    source_user_id = fields.Many2one(
        'res.users',
        string='Source User',
        required=True,
        readonly=True,
        help="User whose permissions will be copied"
    )
    target_user_id = fields.Many2one(
        'res.users',
        string='Target User',
        required=True,
        domain="[('id', '!=', source_user_id), ('id', '!=', 1)]",  # Exclude source user and admin
        help="User who will receive the copied permissions"
    )
    confirmation = fields.Boolean(
        string='I understand that all existing permissions of the target user will be replaced',
        help="Check this box to confirm you understand the consequences"
    )
    
    # Display fields for user information
    source_user_groups = fields.Many2many(
        'res.groups',
        related='source_user_id.groups_id',
        string='Source User Groups',
        readonly=True
    )
    target_user_groups = fields.Many2many(
        'res.groups',
        related='target_user_id.groups_id',
        string='Current Target User Groups',
        readonly=True
    )

    @api.constrains('target_user_id', 'source_user_id')
    def _check_users(self):
        """Validate user selection"""
        for record in self:
            if record.target_user_id and record.source_user_id:
                # Prevent copying to the same user
                if record.target_user_id.id == record.source_user_id.id:
                    raise ValidationError(_("Source and target users cannot be the same."))
                
                # Prevent copying to admin user
                admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
                if admin_user and record.target_user_id.id == admin_user.id:
                    raise ValidationError(_("Cannot modify administrator user permissions."))

    def action_copy_permissions(self):
        """Execute the permission copy operation"""
        self.ensure_one()
        
        _logger.info(
            "Permission copy wizard executed by user %s (ID: %s): copying from %s to %s",
            self.env.user.name, self.env.user.id,
            self.source_user_id.name, self.target_user_id.name
        )
        
        # Validation checks
        if not self.confirmation:
            raise UserError(_("Please confirm that you understand the consequences of this action."))
        
        if not self.source_user_id or not self.target_user_id:
            raise UserError(_("Both source and target users must be selected."))
        
        # Execute the copy operation
        result = self.source_user_id.copy_permissions_to_user(self.target_user_id.id)
        
        return result

    def action_cancel(self):
        """Cancel the wizard"""
        _logger.info(
            "Permission copy wizard cancelled by user %s (ID: %s)",
            self.env.user.name, self.env.user.id
        )
        return {'type': 'ir.actions.act_window_close'}