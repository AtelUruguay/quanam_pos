import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def card_read(self, pos_config_id, is_devolution=False, amount=0):
        """Read the card through the provider configured on the POS.

        Providers implement ``_card_read_<key>(config, is_devolution, amount)`` and
        return a dict with:

        * ``journal_id``: journal of the payment method matching the card (the
          client reports a configuration error when it is missing),
        * ``journal_name``: its name, shown in that error (optional),
        * ``card_last4``: last digits of the card (optional),
        * ``provider_data``: free dict handed back to the client provider (optional),
        * ``mensaje_error``: error message, falsy on success.
        """
        return self._card_dispatch(
            'read', pos_config_id, is_devolution=is_devolution, amount=amount,
        )

    @api.model
    def card_authorize(self, pos_config_id, journal_id, amount, values=None):
        """Authorize a card payment through the provider configured on the POS.

        Providers implement ``_card_authorize_<key>(config, journal_id, amount, values)``
        where ``values`` is the provider specific payload built by its client side
        counterpart. The result is a dict; ``mensaje_error`` (truthy on failure) is the
        only key the core interprets, the others (e.g. ``transaccion_finalizada``,
        ``aprobada``) are provider specific.

        When the POS has no provider, or its provider is not installed, the result
        carries ``mensaje_error`` and ``aprobada: False``. A provider that is not
        installed also sets ``config_error`` so the client does not offer contingency
        for a setup problem.
        """
        return self._card_dispatch(
            'authorize', pos_config_id,
            journal_id=journal_id, amount=amount, values=values or {},
        )

    @api.model
    def _card_dispatch(self, action, pos_config_id, **kwargs):
        config = self.env['pos.config'].browse(pos_config_id).exists()
        # exists() skips ACLs and record rules: the caller must be able to read the POS.
        config.check_access('read')
        provider = config.card_provider
        if not provider:
            return self._card_error(action, self._card_not_configured_message())
        handler = provider.isidentifier() and getattr(
            self, f'_card_{action}_{provider}', None,
        )
        if not handler:
            _logger.warning(
                "card_%s: provider %r of POS config %s has no handler (module not installed?)",
                action, provider, config.id,
            )
            return self._card_error(action, _(
                "La integración de tarjetas «%s» no está disponible en el servidor.", provider,
            ), config_error=True)
        return handler(config, **kwargs)

    @api.model
    def _card_error(self, action, message, config_error=False):
        result = {'mensaje_error': message}
        if action == 'authorize':
            result['aprobada'] = False
        if config_error:
            result['config_error'] = True
        return result

    @api.model
    def _card_not_configured_message(self):
        return _("No tiene configurada integración para pagos de tarjeta")
