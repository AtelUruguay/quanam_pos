import { registry } from "@web/core/registry";

/**
 * Client side counterpart of every card payment provider, keyed like the
 * provider selected in `pos.config.card_provider`.
 *
 * A provider is a plain object; every member is optional:
 *   - onCardRead(screen, line, result): copy provider specific data of the
 *     `pos.order.card_read` result (`result.provider_data`) into the new line.
 *   - authorize(screen, line): charge the line once it has been added.
 */
export const cardProviderRegistry = registry.category("pos_card_providers");
