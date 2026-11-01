// Area chooser used by Compare Providers and Insights: search, "All India" and "Near me".
import { api } from "./api.js";
import { createAreaPicker } from "./area-picker.js";
import { h, icon } from "./dom.js";
import { encode } from "./geohash.js";
import { requestLocation } from "./location.js";

export function createAreaBar(container, { onChange, onError }) {
  const picker = createAreaPicker(h("div", { class: "area-picker" }), { onSelect: (place) => onChange(place.code) });
  const nearMe = h("button", { type: "button", class: "chip" }, icon("locate", "sm"), "Near me");
  const allIndia = h("button", { type: "button", class: "chip" }, icon("globe", "sm"), "All India");

  nearMe.addEventListener("click", async () => {
    nearMe.disabled = true;
    try {
      const position = await requestLocation("We'll pick the city or district you're in.");
      // Only the ~150 m area code is sent, never the exact position.
      const located = await api.locate(encode(position.lat, position.lng, 7));
      onChange(located.places[located.places.length - 1].code);
    } catch (error) {
      if (error.code !== "cancelled" && error.code !== "denied") onError?.(error);
    } finally {
      nearMe.disabled = false;
    }
  });
  allIndia.addEventListener("click", () => onChange("IN"));

  container.append(picker.input.closest(".area-picker"), h("div", { class: "chip-row" }, nearMe, allIndia));
  return { setLabel: (text) => picker.setValue(text) };
}
