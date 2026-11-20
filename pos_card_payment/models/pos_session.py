from odoo import api, models


class PosSession(models.Model):
    _inherit = 'pos.session'

    @api.model
    def _load_pos_data_models(self, config):
        models_list = super()._load_pos_data_models(config)
        if 'account.journal' not in models_list:
            models_list = models_list + ['account.journal']
        return models_list

    @api.model_create_multi
    def create(self, vals_list):
        sessions = super().create(vals_list)
        # A new session never starts in contingency: the mode is per session.
        for config in sessions.config_id.sudo():
            config._card_close_contingency(self.env.user)
        return sessions

    def get_closing_control_data(self):
        data = super().get_closing_control_data()
        payments = self._get_closed_orders().payment_ids.filtered('card_contingency')
        data['card_contingency'] = {
            'number': len(payments),
            'amount': sum(payments.mapped('amount')),
        }
        return data

    def _validate_session(self, *args, **kwargs):
        result = super()._validate_session(*args, **kwargs)
        for session in self.filtered(lambda s: s.state == 'closed'):
            session.config_id.sudo()._card_close_contingency(self.env.user)
        return result
