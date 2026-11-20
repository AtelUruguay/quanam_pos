{
    'name': 'POS Card Payment',
    'version': '19.0.1.0.0',
    'author': 'Quanam',
    'license': 'OPL-1',
    'category': 'Point of Sale',
    'summary': 'Provider-agnostic card reading for the point of sale',
    'description': """
POS Card Payment
================

Adds a "Leer tarjeta" action to the POS payment screen that delegates the card
reading and authorization to the card payment provider chosen on each POS
configuration. The module itself does not talk to any provider: each
integration is a separate module that

* appends its key to ``pos.config._get_card_provider_selection``,
* implements ``pos.order._card_read_<key>`` and ``pos.order._card_authorize_<key>``,
* registers its client side counterpart in the ``pos_card_providers`` registry.

Client side, a provider registers ``onCardRead(screen, line, result)`` and
``authorize(screen, line)`` in the ``pos_card_providers`` registry, and other
modules can override ``PaymentScreen.cardPaymentUnavailable`` to hide the card
actions on specific orders or ``onCardReadFailed`` to react to a failed read.
See README.md for a step by step guide.

Several providers can be installed at the same time; every POS configuration
uses the one selected in its settings. Without a provider the action reports that
card payments are not configured.

Contingency mode: when the terminal has no connection, the cashier can switch the
register to contingency. The payment methods flagged "replaced by Leer tarjeta"
become selectable and their payments are tagged, every activation is logged with
who and when, the mode ends when the session closes and the closing popup
summarizes the contingency payments.
""",
    'depends': ['point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_config_views.xml',
        'views/card_contingency_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_card_payment/static/src/js/card_provider_registry.js',
            'pos_card_payment/static/src/js/contingency_logic.js',
            'pos_card_payment/static/src/js/pos_store_card.js',
            'pos_card_payment/static/src/js/payment_screen_card.js',
            'pos_card_payment/static/src/js/closing_popup_card.js',
            'pos_card_payment/static/src/xml/payment_screen_card.xml',
            'pos_card_payment/static/src/xml/closing_popup_card.xml',
            'pos_card_payment/static/src/scss/card_payment.scss',
        ],
    },
    'installable': True,
    'auto_install': False,
}
