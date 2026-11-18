from odoo import fields, models


class SimpleScheduledReportColumn(models.Model):
    _name = "simple.scheduled.report.column"
    _description = "Scheduled Report Column"
    _order = "sequence, id"

    report_id = fields.Many2one(
        "simple.scheduled.report", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        "ir.model.fields",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', parent.model_id), ('ttype', 'not in', ('binary',"
        " 'one2many', 'html', 'properties', 'properties_definition', 'json'))]",
    )
