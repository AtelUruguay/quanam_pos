import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { cardProviderRegistry } from "@pos_card_payment/js/card_provider_registry";
import { isContingencyPayment } from "@pos_card_payment/js/contingency_logic";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // The list is computed on every render so it follows the contingency
        // mode, which can also change from other places.
        let allMethods = this.payment_methods_from_config;
        Object.defineProperty(this, "payment_methods_from_config", {
            configurable: true,
            get: () => this._cardFilterMethods(allMethods),
            set: (methods) => {
                allMethods = methods;
            },
        });
    },

    /** Methods replaced by "Leer tarjeta" are only selectable in contingency. */
    _cardFilterMethods(methods) {
        if (this.cardActionsAvailable) {
            const contingency = this.pos.isCardContingency;
            return methods.filter((pm) => !pm.replaced_by_card_reader || contingency);
        }
        return methods;
    },

    /** Client side provider of this POS, or null when none is configured/installed. */
    get cardProvider() {
        const key = this.pos.config.card_provider;
        return key ? cardProviderRegistry.get(key, null) : null;
    },

    /**
     * Extension point: other modules return true to hide the card reading
     * actions on specific orders (e.g. a payment that never uses a card).
     */
    get cardPaymentUnavailable() {
        return false;
    },

    get cardActionsAvailable() {
        return (
            Boolean(this.pos.config.card_provider) &&
            !this.isRefundOrder &&
            !this.cardPaymentUnavailable
        );
    },

    /**
     * Shown even when the POS has no provider: pressing it then explains that card
     * payments are not configured, instead of leaving the cashier without a button.
     */
    get showCardReadButton() {
        return (
            !this.isRefundOrder && !this.cardPaymentUnavailable && !this.pos.isCardContingency
        );
    },

    get cardContingencyActive() {
        return this.pos.isCardContingency;
    },

    get showCardContingencySwitch() {
        return this.cardActionsAvailable && this.pos.canCardContingency;
    },

    /** Offers contingency; it is never turned on without the cashier's confirmation. */
    offerCardContingency() {
        if (!this.pos.canCardContingency || this.pos.isCardContingency) {
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Terminal sin conexión"),
            body: _t("No se pudo conectar con la terminal. ¿Cobrar sin terminal?"),
            confirmLabel: _t("Cobrar sin terminal"),
            confirm: () => this.pos.toggleCardContingency(),
            cancel: () => {},
        });
    },

    /**
     * Tags the payments charged by hand because of contingency: those whose
     * method was unhooked from the terminal by the mode, and those of methods
     * only offered in contingency (`replaced_by_card_reader`). Done on
     * validation, not when the line is added: a line started before the mode
     * was switched on is charged by hand too.
     */
    async validateOrder(isForceValidate) {
        if (this.pos.isCardContingency) {
            for (const line of this.paymentLines) {
                if (isContingencyPayment(line.payment_method_id, this.pos._cardTerminalStash)) {
                    line.card_contingency = true;
                }
            }
        }
        return super.validateOrder(...arguments);
    },

    /** Called with the message when reading the card failed; providers may extend it. */
    onCardReadFailed(message) {
        this.offerCardContingency();
    },

    async readCard() {
        if (this.pos.paymentTerminalInProgress) {
            this.notification.add(_t("Ya hay un pago electrónico en curso."), { type: "danger" });
            return;
        }
        const provider = this.cardProvider;
        if (!provider) {
            this.notification.add(
                _t("No tiene configurada integración para pagos de tarjeta"),
                { type: "danger" }
            );
            return;
        }
        const line = await this._cardReadLine(provider);
        if (line) {
            await this._cardAuthorizeLine(provider, line);
        }
    },

    /** Reads the card and adds its payment line; returns the line, or null on failure. */
    async _cardReadLine(provider) {
        try {
            const amount = Math.abs(this.currentOrder.remainingDue);
            const result = await this.env.services.orm.call("pos.order", "card_read", [
                this.pos.config.id,
                false,
                amount,
            ]);
            if (result.mensaje_error) {
                this.notification.add(result.mensaje_error, { type: "danger" });
                // A setup problem is not a terminal outage: contingency would hide it.
                if (!result.config_error) {
                    this.onCardReadFailed(result.mensaje_error);
                }
                return null;
            }
            const paymentMethod = this.pos.config.payment_method_ids.find(
                (pm) => pm.journal_id?.id === result.journal_id
            );
            if (!paymentMethod) {
                await this.dialog.add(AlertDialog, {
                    title: _t("Error de configuración en el sistema"),
                    body: _t(
                        "El administrador debe agregar el medio de pago %s a la lista de medios de pago disponibles de este TPV.",
                        result.journal_name || result.journal_id
                    ),
                });
                return null;
            }
            if (!(await this.addNewPaymentLine(paymentMethod))) {
                return null;
            }
            const line = this.paymentLines.at(-1);
            line.card_no = result.card_last4 || false;
            await provider.onCardRead?.(this, line, result);
            return line;
        } catch (error) {
            const message =
                error?.data?.message || error?.message || _t("Error de comunicación con la terminal.");
            this.notification.add(message, { type: "danger" });
            this.onCardReadFailed(message);
            return null;
        }
    },

    /**
     * Charges the line. A failure here is not offered as contingency: the card
     * was read and the terminal may have charged it, so the cashier has to
     * check it and retry the line.
     */
    async _cardAuthorizeLine(provider, line) {
        if (!provider.authorize) {
            this.notification.add(
                _t("La integración de tarjetas no puede autorizar el pago."),
                { type: "danger" }
            );
            return;
        }
        try {
            await provider.authorize(this, line);
        } catch (error) {
            const message =
                error?.data?.message || error?.message || _t("Error al autorizar el pago.");
            this.notification.add(
                _t("%s Verifique el estado del cobro en la terminal antes de reintentar.", message),
                { type: "danger" }
            );
        }
    },
});
