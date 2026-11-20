# pos_card_payment

Provider-agnostic card reading for the Odoo point of sale. The module talks to no
card provider: each integration is its own small module that plugs into the seam
below. Several providers can be installed together; each POS configuration picks
one in `card_provider`.

## What the core does

* "Leer tarjeta" button on the payment screen, shown only when the POS has a provider.
* Server entry points `pos.order.card_read` / `pos.order.card_authorize`, which
  dispatch to the provider chosen on the POS config.
* Contingency mode (terminal without connection): toggle, payment methods flagged
  `replaced_by_card_reader` become selectable, payments tagged, log of who/when,
  summary in the closing popup, ends when the session closes.

## Adding a provider

A provider module depends on `pos_card_payment` and has three parts.

### 1. Register the provider key

```python
class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def _get_card_provider_selection(self):
        return super()._get_card_provider_selection() + [('myprovider', 'My provider')]
```

### 2. Implement the server side

```python
class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _card_read_myprovider(self, config, is_devolution, amount):
        # Talk to the terminal. Return:
        #   journal_id    journal of the payment method matching the card
        #   journal_name  its name (shown if the method is missing on the POS)
        #   card_last4    optional
        #   provider_data optional dict handed to the client side onCardRead
        #   mensaje_error truthy on failure
        return {'journal_id': 12, 'card_last4': '4242', 'provider_data': {'token': 'abc'}}

    @api.model
    def _card_authorize_myprovider(self, config, journal_id, amount, values):
        # `values` is whatever the client side sends. mensaje_error (truthy on
        # failure) is the only key the core interprets.
        return {'aprobada': True, 'mensaje_error': False}
```

A POS whose provider key has no handler gets a configuration error (and a server
warning) instead of the "no integration" message.

### 3. Register the client side

```js
import { cardProviderRegistry } from "@pos_card_payment/js/card_provider_registry";

cardProviderRegistry.add("myprovider", {
    // Called after the card was read and its payment line added.
    onCardRead(screen, line, result) {
        line.my_token = result.provider_data?.token;
    },
    // Charges the line. If it throws, the cashier is told to check the terminal;
    // contingency is not offered for a failed charge.
    async authorize(screen, line) {
        await screen.sendPaymentRequest(line);
    },
});
```

Add the file to `point_of_sale._assets_pos` in the manifest. Both hooks are
optional, but without `authorize` the read card is never charged.

### Extension points

* `PaymentScreen.cardPaymentUnavailable` (getter): return true to hide the card
  actions on specific orders.
* `PaymentScreen.onCardReadFailed(message)`: called when the read fails.

### Migrating data from a previous integration

The contingency fields live in this module (`card_allow_contingency`,
`card_contingency_active`, `card.contingency.log`, `pos.payment.card_contingency`,
`pos.payment.method.replaced_by_card_reader`); a provider module that had its own
copies must copy them in a post-migration (see
`la_isla_integration_transact/migrations/19.0.2.0.0`).
