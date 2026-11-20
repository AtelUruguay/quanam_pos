from odoo import api, models


class AccountJournal(models.Model):
    _name = 'account.journal'
    _inherit = ['account.journal', 'pos.load.mixin']

    @api.model
    def _load_pos_data_domain(self, data, config):
        # The card flow resolves the payment method of a read card by its journal, so
        # only the journals of the POS payment methods are loaded, with the bare
        # minimum of fields; provider modules extend them (Transact does).
        return [('id', 'in', config.payment_method_ids.journal_id.ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'name']
