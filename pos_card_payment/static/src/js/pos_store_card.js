import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { _t } from "@web/core/l10n/translation";
import {
    isCardTerminalMethod,
    resetStartedTerminalLines,
    syncTerminalStash,
} from "@pos_card_payment/js/contingency_logic";

/**
 * Contingency mode: while the terminal has no connection, the payment methods
 * hooked to the terminal that are flagged `replaced_by_card_reader`, or whose
 * terminal is the POS provider's, are unhooked from it so they are charged by
 * hand, and hooked back when the mode is turned off. The flag alone decides which
 * methods are hidden in normal mode. Lines already started on the terminal
 * ("pending"/"retry") would keep blocking new payment lines ("there is already
 * an electronic payment in progress"), so they are reset to manual lines and the
 * cashier is told, because the terminal may have charged them.
 */
patch(PosStore.prototype, {
    async processServerData() {
        await super.processServerData(...arguments);
        this._applyCardContingency();
    },

    get canCardContingency() {
        return Boolean(this.config.card_provider && this.config.card_allow_contingency);
    },

    get isCardContingency() {
        return this.canCardContingency && Boolean(this.config.card_contingency_active);
    },

    get _cardTerminalStash() {
        return (this._cardStash ||= new Map());
    },

    _applyCardContingency() {
        const contingency = this.isCardContingency;
        syncTerminalStash(this.models["pos.payment.method"].getAll(), this._cardTerminalStash, {
            contingency,
            provider: this.config.card_provider,
        });
        if (contingency) {
            this._notifyResetTerminalLines();
        }
    },

    _isCardTerminalMethod(pm) {
        return isCardTerminalMethod(pm, this.config.card_provider);
    },

    /** Resets lines started on the terminal whose method was unhooked, and warns about them. */
    _notifyResetTerminalLines() {
        const names = resetStartedTerminalLines(
            this.models["pos.payment"].getAll(),
            this._cardTerminalStash
        );
        if (names.length) {
            this.notification.add(
                _t(
                    "Se pasaron a cobro manual: %s. Verifique en la terminal si el cobro llegó a realizarse.",
                    names.join(", ")
                ),
                { type: "warning" }
            );
        }
    },

    async setCardContingency(active) {
        const result = await this.data.call("pos.config", "set_card_contingency", [
            [this.config.id],
            active,
        ]);
        this.config.card_contingency_active = result;
        this._applyCardContingency();
        return result;
    },

    /** Changes the mode from any screen; never while an electronic payment is running. */
    async toggleCardContingency() {
        if (this.paymentTerminalInProgress) {
            this.notification.add(_t("Ya hay un pago electrónico en curso."), { type: "danger" });
            return;
        }
        try {
            await this.setCardContingency(!this.isCardContingency);
        } catch (error) {
            this.notification.add(
                error?.data?.message || error?.message || _t("No se pudo cambiar el modo contingencia."),
                { type: "danger" }
            );
        }
    },
});
