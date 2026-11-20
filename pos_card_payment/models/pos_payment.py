from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    replaced_by_card_reader = fields.Boolean(
        string='Se reemplaza por «Leer tarjeta»',
        help='En una caja con proveedor de pagos con tarjeta, este método se oculta y lo reemplaza '
             '«Leer tarjeta». Solo se ofrece en modo contingencia.',
    )

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        for name in ('journal_id', 'replaced_by_card_reader'):
            if name not in fields:
                fields = fields + [name]
        return fields


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    card_contingency = fields.Boolean('Cobrado en contingencia', copy=False)
