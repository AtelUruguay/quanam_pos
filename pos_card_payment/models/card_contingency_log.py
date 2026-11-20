from odoo import fields, models


class CardContingencyLog(models.Model):
    _name = 'card.contingency.log'
    _description = 'POS card contingency mode log'
    _order = 'id desc'

    config_id = fields.Many2one('pos.config', string='Punto de venta', required=True, ondelete='cascade', index=True)
    session_id = fields.Many2one('pos.session', string='Sesión', required=True, ondelete='cascade', index=True)
    activated_by_id = fields.Many2one('res.users', string='Activado por', required=True)
    activated_date = fields.Datetime(string='Activado el', required=True, default=fields.Datetime.now)
    deactivated_by_id = fields.Many2one('res.users', string='Desactivado por')
    deactivated_date = fields.Datetime(string='Desactivado el')
    closed_with_session = fields.Boolean(string='Apagado al cerrar la sesión')
