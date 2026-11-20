from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCardContingency(TransactionCase):

    def setUp(self):
        super().setUp()
        patcher = patch.object(
            type(self.env['pos.config']), '_get_card_provider_selection',
            lambda self: [('fake', 'Fake provider')],
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = self.env['pos.config'].create({
            'name': 'Card register',
            'card_provider': 'fake',
            'card_allow_contingency': True,
        })
        self.config.open_ui()
        self.session = self.config.current_session_id

    def _logs(self):
        return self.env['card.contingency.log'].search([('config_id', '=', self.config.id)])

    def test_default_is_normal_mode(self):
        self.assertFalse(self.config.card_contingency_active)

    def test_activate_and_deactivate_register_who_and_when(self):
        self.config.set_card_contingency(True)
        self.assertTrue(self.config.card_contingency_active)
        log = self._logs()
        self.assertEqual(len(log), 1)
        self.assertEqual(log.session_id, self.session)
        self.assertEqual(log.activated_by_id, self.env.user)
        self.assertTrue(log.activated_date)
        self.assertFalse(log.deactivated_date)

        self.config.set_card_contingency(False)
        self.assertFalse(self.config.card_contingency_active)
        self.assertEqual(log.deactivated_by_id, self.env.user)
        self.assertTrue(log.deactivated_date)
        self.assertFalse(log.closed_with_session)

    def test_setting_same_state_does_not_duplicate_log(self):
        self.config.set_card_contingency(True)
        self.config.set_card_contingency(True)
        self.assertEqual(len(self._logs()), 1)

    def test_other_config_is_not_affected(self):
        other = self.config.copy({'name': 'Other register'})
        self.config.set_card_contingency(True)
        self.assertFalse(other.card_contingency_active)

    def test_requires_provider(self):
        self.config.card_provider = False
        with self.assertRaises(UserError):
            self.config.set_card_contingency(True)
        self.assertFalse(self.config.card_contingency_active)

    def test_requires_option_enabled(self):
        self.config.card_allow_contingency = False
        with self.assertRaises(UserError):
            self.config.set_card_contingency(True)

    def test_closing_session_turns_contingency_off(self):
        self.config.set_card_contingency(True)
        self.session.action_pos_session_closing_control()
        self.assertEqual(self.session.state, 'closed')
        self.assertFalse(self.config.card_contingency_active)
        log = self._logs()
        self.assertTrue(log.closed_with_session)
        self.assertTrue(log.deactivated_date)

    def test_closing_control_data_reports_contingency_payments(self):
        data = self.session.get_closing_control_data()
        self.assertEqual(data['card_contingency'], {'number': 0, 'amount': 0})

    def test_payment_method_loads_replaced_by_card_reader(self):
        fields = self.env['pos.payment.method']._load_pos_data_fields(self.config)
        self.assertIn('replaced_by_card_reader', fields)
        self.assertIn('journal_id', fields)

    def test_journals_are_loaded_in_pos(self):
        self.assertIn('account.journal', self.env['pos.session']._load_pos_data_models(self.config))

    def test_set_returns_the_persisted_state(self):
        self.assertTrue(self.config.set_card_contingency(True))
        self.assertEqual(self.config.card_contingency_active, True)
        self.assertFalse(self.config.set_card_contingency(False))
        self.assertEqual(self.config.card_contingency_active, False)

    def test_user_without_pos_rights_cannot_change_the_mode(self):
        user = self.env['res.users'].create({
            'name': 'No POS', 'login': 'no_pos_card', 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.config.with_user(user).set_card_contingency(True)
        self.assertFalse(self.config.card_contingency_active)

    def test_deactivating_only_closes_the_log_of_the_current_session(self):
        Log = self.env['card.contingency.log']
        stale = Log.create({
            'config_id': self.config.id,
            'session_id': self.env['pos.session'].create({
                'config_id': self.config.copy({'name': 'Elsewhere'}).id,
                'user_id': self.env.user.id,
            }).id,
            'activated_by_id': self.env.user.id,
        })
        self.config.set_card_contingency(True)
        self.config.set_card_contingency(False)
        self.assertFalse(stale.deactivated_date)
        self.assertTrue(self._logs().filtered(lambda l: l.session_id == self.session).deactivated_date)

    def test_close_contingency_ends_open_logs_even_if_the_flag_is_off(self):
        """A crashed session can leave an open log behind with the flag already off."""
        log = self.env['card.contingency.log'].create({
            'config_id': self.config.id,
            'session_id': self.session.id,
            'activated_by_id': self.env.user.id,
        })
        self.assertFalse(self.config.card_contingency_active)
        self.config._card_close_contingency(self.env.user)
        self.assertTrue(log.deactivated_date)
        self.assertTrue(log.closed_with_session)

    def test_a_new_session_does_not_start_in_contingency(self):
        self.config.set_card_contingency(True)
        log = self._logs()
        # The session disappears without going through the closing flow.
        self.session.sudo().write({'state': 'closed'})
        self.config.open_ui()
        self.assertNotEqual(self.config.current_session_id, self.session)
        self.assertFalse(self.config.card_contingency_active)
        self.assertTrue(log.closed_with_session)

    def test_session_that_stays_open_keeps_contingency(self):
        """The hook only acts on sessions that really ended up closed."""
        from odoo.addons.point_of_sale.models.pos_session import PosSession as CoreSession
        self.config.set_card_contingency(True)
        with patch.object(CoreSession, '_validate_session', lambda self, *a, **k: True):
            self.session._validate_session()
        self.assertNotEqual(self.session.state, 'closed')
        self.assertTrue(self.config.card_contingency_active)
        self.assertFalse(self._logs().deactivated_date)
