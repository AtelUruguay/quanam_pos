import { test } from "node:test";
import assert from "node:assert/strict";

import {
    isCardTerminalMethod,
    isContingencyPayment,
    resetStartedTerminalLines,
    syncTerminalStash, isCardRequestMethod } from "../src/js/contingency_logic.js";

const terminal = { name: "terminal" };

function method(id, extra = {}) {
    return {
        id,
        name: `pm${id}`,
        use_payment_terminal: "transact",
        payment_terminal: terminal,
        ...extra,
    };
}

const on = { contingency: true, provider: "transact" };
const off = { contingency: false, provider: "transact" };

test("a method is taken over when flagged or when its terminal is the provider's", () => {
    assert.equal(isCardTerminalMethod(method(1), "transact"), true);
    assert.equal(isCardTerminalMethod(method(1, { use_payment_terminal: "other" }), "transact"), false);
    assert.equal(
        isCardTerminalMethod(
            method(1, { use_payment_terminal: "other", replaced_by_card_reader: true }),
            "transact"
        ),
        true
    );
});

test("contingency unhooks the terminal and turning it off restores it", () => {
    const pm = method(1);
    const stash = new Map();
    syncTerminalStash([pm], stash, on);
    assert.equal(pm.use_payment_terminal, false);
    assert.equal(pm.payment_terminal, undefined);

    syncTerminalStash([pm], stash, off);
    assert.equal(pm.use_payment_terminal, "transact");
    assert.equal(pm.payment_terminal, terminal);
    assert.equal(stash.size, 0);
});

test("applying contingency twice does not overwrite the stash with the unhooked values", () => {
    const pm = method(1);
    const stash = new Map();
    syncTerminalStash([pm], stash, on);
    syncTerminalStash([pm], stash, on);
    syncTerminalStash([pm], stash, off);
    assert.equal(pm.use_payment_terminal, "transact");
    assert.equal(pm.payment_terminal, terminal);
});

test("methods of another terminal or without terminal are left alone", () => {
    const other = method(2, { use_payment_terminal: "other" });
    const manual = method(3, { use_payment_terminal: false, payment_terminal: undefined });
    const stash = new Map();
    syncTerminalStash([other, manual], stash, on);
    assert.equal(other.use_payment_terminal, "other");
    assert.equal(manual.use_payment_terminal, false);
    assert.equal(stash.size, 0);
});

test("a method that is not stashed is not touched when the mode is off", () => {
    const pm = method(1);
    syncTerminalStash([pm], new Map(), off);
    assert.equal(pm.use_payment_terminal, "transact");
});

test("a stash entry the provider module dropped is not restored", () => {
    // The Transact module unhooks the terminal of POS that must not use it and
    // forgets it in the stash; ending contingency must not hook it back.
    const pm = method(1);
    const stash = new Map();
    syncTerminalStash([pm], stash, on);
    stash.delete(pm.id);
    syncTerminalStash([pm], stash, off);
    assert.equal(pm.use_payment_terminal, false);
});

test("only started lines of unhooked methods are reset, and their methods reported", () => {
    const stash = new Map([[1, {}]]);
    const lines = [
        { payment_method_id: { id: 1, name: "Visa" }, payment_status: "pending" },
        { payment_method_id: { id: 1, name: "Visa" }, payment_status: "retry" },
        { payment_method_id: { id: 1, name: "Visa" }, payment_status: "done" },
        { payment_method_id: { id: 2, name: "Cash" }, payment_status: "pending" },
    ];
    assert.deepEqual(resetStartedTerminalLines(lines, stash), ["Visa"]);
    assert.deepEqual(
        lines.map((l) => l.payment_status),
        [undefined, undefined, "done", "pending"]
    );
});

test("nothing is reported when no line was reset", () => {
    assert.deepEqual(resetStartedTerminalLines([], new Map()), []);
});

test("contingency payments are those of unhooked or flagged methods", () => {
    const stash = new Map([[1, {}]]);
    assert.equal(isContingencyPayment({ id: 1 }, stash), true);
    assert.equal(isContingencyPayment({ id: 2, replaced_by_card_reader: true }, stash), true);
    assert.equal(isContingencyPayment({ id: 3 }, stash), false);
});

test("only methods that start a card request are blocked while one is pending", () => {
    assert.equal(isCardRequestMethod({ use_payment_terminal: "transact" }), true);
    assert.equal(isCardRequestMethod({ replaced_by_card_reader: true }), true);
    assert.equal(isCardRequestMethod({ use_payment_terminal: false }), false);
    assert.equal(isCardRequestMethod({}), false);
});
