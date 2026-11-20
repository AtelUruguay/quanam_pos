import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";

// get_closing_control_data also returns the contingency summary and the popup
// validates its props, so the new one has to be declared.
ClosePosPopup.props = [...ClosePosPopup.props, "card_contingency?"];
