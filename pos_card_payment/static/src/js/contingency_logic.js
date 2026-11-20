/**
 * Pure rules of the contingency mode, kept free of Odoo imports so they can be
 * unit tested with `node --test` (see ../../tests).
 */

/** A method the mode takes over: flagged as replaced by the reader, or hooked to the POS provider. */
export function isCardTerminalMethod(pm, provider) {
    return Boolean(pm.replaced_by_card_reader || pm.use_payment_terminal === provider);
}

/** A method that starts a card request (terminal hooked, or replaced by "Leer tarjeta"). */
export function isCardRequestMethod(pm) {
    return Boolean(pm.use_payment_terminal || pm.replaced_by_card_reader);
}

/**
 * Unhooks (contingency on) or hooks back (contingency off) the terminal of the
 * payment methods. `stash` remembers what was unhooked; a method already
 * unhooked is never stashed again, so toggling twice cannot lose the terminal.
 */
export function syncTerminalStash(methods, stash, { contingency, provider }) {
    for (const pm of methods) {
        if (contingency && pm.use_payment_terminal && isCardTerminalMethod(pm, provider)) {
            stash.set(pm.id, {
                use_payment_terminal: pm.use_payment_terminal,
                payment_terminal: pm.payment_terminal,
            });
            pm.use_payment_terminal = false;
            pm.payment_terminal = undefined;
        } else if (!contingency && stash.has(pm.id)) {
            Object.assign(pm, stash.get(pm.id));
            stash.delete(pm.id);
        }
    }
}

/**
 * Lines started on the terminal ("pending"/"retry") of an unhooked method would
 * keep blocking new payment lines, so they become manual lines. Returns the
 * names of the affected methods so the cashier can be told.
 */
export function resetStartedTerminalLines(lines, stash) {
    const names = new Set();
    for (const line of lines) {
        const pm = line.payment_method_id;
        if (["pending", "retry"].includes(line.payment_status) && stash.has(pm.id)) {
            line.payment_status = undefined;
            names.add(pm.name);
        }
    }
    return [...names];
}

/** Payments charged by hand because of the mode: unhooked methods and the ones only offered in contingency. */
export function isContingencyPayment(pm, stash) {
    return stash.has(pm.id) || Boolean(pm.replaced_by_card_reader);
}
