# quanam_pos

Odoo 19 point of sale add-ons by Quanam. The modules are product-like: they depend
only on Odoo standard modules, never on a specific customer.

## Modules

| Module | Depends on | What it does |
| --- | --- | --- |
| [`pos_card_payment`](pos_card_payment/README.md) | `point_of_sale` | Provider-agnostic card reading and authorization on the payment screen, one provider per POS, and a contingency mode for terminals without connection. |

`pos_card_payment` talks to no card provider. Each integration (for example a
terminal vendor's SOAP or REST service) is a small separate module that registers
itself in the core. See [Adding a provider](pos_card_payment/README.md#adding-a-provider).

## Installing

Add this repository to the `addons_path` and install the module from Apps.

As a git submodule (Odoo.sh or any repository that tracks it):

```bash
git submodule add -b main https://github.com/AtelUruguay/quanam_pos.git SUBMODULE/quanam_pos
```

The repository is public, so Odoo.sh clones it over HTTPS without a deploy key.

## Running the tests

Install the module on a database that has only the Odoo standard modules, then:

```bash
odoo-bin -d <db> -i pos_card_payment --test-enable --test-tags /pos_card_payment --stop-after-init
```

The contingency rules are a pure JavaScript module with plain Node tests (no Odoo needed):

```bash
node --test pos_card_payment/static/tests/contingency_logic.test.mjs
```

## Contributing

* `main` is protected: changes go through a pull request, merged with squash or
  rebase (the history is linear).
* Use Conventional Commits (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`),
  with the module name as scope, for example `fix(pos_card_payment): ...`.
* Keep modules free of customer-specific code. A customer module that consumes one
  of these lives in the customer's repository and depends on it, never the reverse.
* Every behavior change comes with a test, and the module README is updated when a
  public hook (provider methods, JS registry, getters) changes.

## License

Each module declares its license in its `__manifest__.py`.
