import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class IrListviewColumnPreset(models.Model):
    _name = "ir.listview.column.preset"
    _description = "List View Column Preset"
    _order = "name"

    name = fields.Char(string="Preset Name", required=True)
    model_id = fields.Char(required=True, index=True)
    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        index=True,
        help="Empty for shared presets available to all users",
    )
    column_fields = fields.Text(required=True, help="JSON array of field names")
    is_shared = fields.Boolean(
        string="Shared", compute="_compute_is_shared", store=True
    )
    parent_model_id = fields.Char(
        help="For embedded lists, the parent form's model (e.g. sale.order)",
    )
    relational_field = fields.Char(
        help="For embedded lists, the parent form's field (e.g. order_line)",
    )

    @api.depends("user_id")
    def _compute_is_shared(self):
        for record in self:
            record.is_shared = not record.user_id

    @api.model
    def get_presets(self, model_name, parent_model=None, relational_field=None):
        """Get all presets available for the current user for a given model.

        Args:
            model_name: The model name (e.g., 'sale.order.line')
            parent_model, relational_field: embedded-list context, unused
                (a preset belongs to the model, wherever its list is shown)
        """
        domain = [
            ("model_id", "=", model_name),
            "|",
            ("user_id", "=", self.env.uid),
            ("user_id", "=", False),
        ]
        # Note: context parameters are accepted but not used in filtering
        # This allows for future enhancement to separate presets by context
        presets = self.search(domain)
        return [
            {
                "id": preset.id,
                "name": preset.name,
                "is_shared": preset.is_shared,
                "is_own": preset.user_id.id == self.env.uid
                if preset.user_id
                else False,
                "column_fields": json.loads(preset.column_fields),
            }
            for preset in presets
        ]

    @api.model
    def save_preset(
        self,
        model_name,
        name,
        columns,
        is_shared=False,
        parent_model=None,
        relational_field=None,
    ):
        """Save a new column preset.

        Args:
            model_name: The model name (e.g., 'sale.order.line')
            name: Preset name
            columns: List of column field names
            is_shared: Whether the preset is shared
            parent_model, relational_field: embedded-list context, stored only
        """
        # Check permission for shared presets
        if is_shared and not self.env.user.has_group(
            "web_listview_column_presets.group_shared_presets"
        ):
            raise AccessError(_("You don't have permission to create shared presets."))

        values = {
            "name": name,
            "model_id": model_name,
            "user_id": False if is_shared else self.env.uid,
            "column_fields": json.dumps(columns),
            "parent_model_id": parent_model,
            "relational_field": relational_field,
        }
        preset = self.create(values)
        return {
            "id": preset.id,
            "name": preset.name,
            "is_shared": preset.is_shared,
            "is_own": not is_shared,
            "column_fields": columns,
        }

    def delete_preset(self):
        """Delete a preset with permission check."""
        self.ensure_one()
        if self.user_id and self.user_id.id != self.env.uid:
            raise AccessError(_("You can only delete your own presets."))
        if not self.user_id and not self.env.user.has_group(
            "web_listview_column_presets.group_shared_presets"
        ):
            raise AccessError(_("You don't have permission to delete shared presets."))
        self.unlink()
        return True
