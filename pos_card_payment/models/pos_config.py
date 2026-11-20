import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    card_provider = fields.Selection(
        selection='_get_card_provider_selection',
        string='Card provider',
        help='Integration used by the "Leer tarjeta" action of this point of sale. '
             'Leave empty if the point of sale has no card integration.',
    )
    card_allow_contingency = fields.Boolean(
        string='Permitir modo contingencia',
        help='Permite al cajero pasar la caja a modo contingencia cuando la terminal no funciona. '
             'Solo tiene efecto si la caja tiene un proveedor de pagos con tarjeta.',
    )
    card_contingency_active = fields.Boolean(
        string='Modo contingencia activo',
        copy=False,
        readonly=True,
        help='Estado operativo de la caja: la terminal integrada no está disponible ahora.',
    )

    @api.model
    def _get_card_provider_selection(self):
        """Extension point: provider modules append ``(key, label)`` tuples."""
        return []

    def set_card_contingency(self, active):
        """Called from the POS payment screen by the cashier."""
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tenés permisos para cambiar el modo contingencia."))
        active = bool(active)
        if not (self.card_provider and self.card_allow_contingency):
            raise UserError(_("El modo contingencia no está habilitado en esta caja."))
        session = self.current_session_id
        if not session:
            raise UserError(_("La caja no tiene una sesión abierta."))
        self.sudo()._card_set_contingency(active, session, self.env.user)
        # The persisted state, not the requested one: another cashier or tab may
        # have changed it meanwhile and the client must end up in sync with it.
        return self.card_contingency_active

    def _card_set_contingency(self, active, session, user):
        """Change the state and log it on the session (who and when)."""
        self.ensure_one()
        if self.card_contingency_active == active:
            return
        Log = self.env['card.contingency.log']
        if active:
            Log.create({
                'config_id': self.id,
                'session_id': session.id,
                'activated_by_id': user.id,
            })
        else:
            logs = Log.search([
                ('config_id', '=', self.id),
                ('session_id', '=', session.id),
                ('deactivated_date', '=', False),
            ])
            if not logs:
                _logger.warning(
                    "Contingency of POS config %s turned off with no open log in session %s",
                    self.id, session.id,
                )
            logs.write({
                'deactivated_by_id': user.id,
                'deactivated_date': fields.Datetime.now(),
            })
        self.card_contingency_active = active

    def _card_close_contingency(self, user):
        """Contingency does not outlive the session: it is turned off when it closes.

        Also called when a session opens, which ends the contingency (and its open
        log) that a crashed or force-closed session left behind.
        """
        self.ensure_one()
        self.env['card.contingency.log'].search([
            ('config_id', '=', self.id),
            ('deactivated_date', '=', False),
        ]).write({
            'deactivated_by_id': user.id,
            'deactivated_date': fields.Datetime.now(),
            'closed_with_session': True,
        })
        if self.card_contingency_active:
            self.card_contingency_active = False
