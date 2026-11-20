from unittest.mock import patch

from odoo.addons.pos_card_payment.models.pos_config import PosConfig
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestCardDispatch(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['pos.config'].create({'name': 'Card register'})
        self.order_model = self.env['pos.order']
        self.not_configured = self.order_model._card_not_configured_message()

    def _with_provider(self, handlers=None):
        """Install a fake provider ``fake`` on the registry classes for one test."""
        config_cls = type(self.env['pos.config'])
        order_cls = type(self.order_model)
        stack = [patch.object(
            config_cls, '_get_card_provider_selection',
            lambda self: [('fake', 'Fake provider')],
        )]
        for name, handler in (handlers or {}).items():
            stack.append(patch.object(order_cls, name, handler, create=True))
        for p in stack:
            p.start()
            self.addCleanup(p.stop)
        self.config.card_provider = 'fake'

    def test_no_provider_selected(self):
        self.assertFalse(self.config.card_provider)
        result = self.order_model.card_read(self.config.id, False, 10)
        self.assertEqual(result, {'mensaje_error': self.not_configured})
        result = self.order_model.card_authorize(self.config.id, 1, 10)
        self.assertEqual(result, {'mensaje_error': self.not_configured, 'aprobada': False})

    def test_provider_without_implementation(self):
        """A provider key without handler is a setup problem, not "not configured"."""
        self._with_provider()
        with self.assertLogs('odoo.addons.pos_card_payment.models.pos_order', 'WARNING') as logs:
            result = self.order_model.card_read(self.config.id, False, 10)
        self.assertIn("'fake'", logs.output[0])
        self.assertTrue(result['config_error'])
        self.assertIn('fake', result['mensaje_error'])
        self.assertNotEqual(result['mensaje_error'], self.not_configured)
        result = self.order_model.card_authorize(self.config.id, 1, 10)
        self.assertEqual((result['aprobada'], result['config_error']), (False, True))

    def test_cashier_can_use_the_card_actions(self):
        self._with_provider({'_card_read_fake': lambda order, config, is_devolution, amount: {'journal_id': 1}})
        cashier = new_test_user(self.env, login='card_cashier', groups='point_of_sale.group_pos_user')
        result = self.order_model.with_user(cashier).card_read(self.config.id, False, 10)
        self.assertEqual(result['journal_id'], 1)

    def test_user_without_pos_access_is_rejected(self):
        self._with_provider({'_card_read_fake': lambda order, config, is_devolution, amount: {'journal_id': 1}})
        outsider = new_test_user(self.env, login='card_outsider', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.order_model.with_user(outsider).card_read(self.config.id, False, 10)
        with self.assertRaises(AccessError):
            self.order_model.with_user(outsider).card_authorize(self.config.id, 1, 10)

    def test_unknown_config(self):
        result = self.order_model.card_read(0, False, 10)
        self.assertEqual(result, {'mensaje_error': self.not_configured})

    def test_read_is_dispatched_to_the_selected_provider(self):
        calls = []

        def read(order, config, is_devolution, amount):
            calls.append((config, is_devolution, amount))
            return {'journal_id': 7, 'card_last4': '1234', 'mensaje_error': False}

        self._with_provider({'_card_read_fake': read})
        result = self.order_model.card_read(self.config.id, True, 25.5)
        self.assertEqual(result['journal_id'], 7)
        self.assertEqual(calls, [(self.config, True, 25.5)])

    def test_authorize_is_dispatched_with_provider_values(self):
        calls = []

        def authorize(order, config, journal_id, amount, values):
            calls.append((config, journal_id, amount, values))
            return {'transaccion_finalizada': True, 'aprobada': True, 'mensaje_error': False}

        self._with_provider({'_card_authorize_fake': authorize})
        result = self.order_model.card_authorize(self.config.id, 3, 50, {'token': 'abc'})
        self.assertTrue(result['aprobada'])
        self.assertEqual(calls, [(self.config, 3, 50, {'token': 'abc'})])

    def test_other_config_does_not_use_the_provider(self):
        def read(order, config, is_devolution, amount):
            return {'journal_id': 1}

        self._with_provider({'_card_read_fake': read})
        other = self.env['pos.config'].create({'name': 'Other register'})
        result = self.order_model.card_read(other.id, False, 10)
        self.assertEqual(result, {'mensaje_error': self.not_configured})

    def test_provider_selection_is_empty_by_default(self):
        # Call the base implementation: provider modules installed in the same
        # database extend the selection through the MRO.
        base = PosConfig._get_card_provider_selection
        self.assertEqual(base(self.env['pos.config']), [])
