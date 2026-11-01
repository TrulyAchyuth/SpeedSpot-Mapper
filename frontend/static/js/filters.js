// Time-period and provider filters, shared by the map, Compare Providers and Insights.
// The current choice lives in the URL (?period=&provider=) so views can be shared.
import { api } from "./api.js";
import { h } from "./dom.js";

export const PERIODS = [
  { value: "", label: "Last 6 months" },
  { value: "90", label: "Last 3 months" },
  { value: "30", label: "Last 30 days" },
  { value: "7", label: "Last 7 days" },
];

let providerOptions = null;
async function loadProviders() {
  if (!providerOptions) {
    providerOptions = api.providers().catch(() => []);
  }
  return providerOptions;
}

export function readFilters() {
  const params = new URLSearchParams(window.location.search);
  return { period: params.get("period") || "", provider: params.get("provider") || "" };
}

function writeFilters(filters) {
  const url = new URL(window.location.href);
  for (const key of ["period", "provider"]) {
    if (filters[key]) url.searchParams.set(key, filters[key]);
    else url.searchParams.delete(key);
  }
  history.replaceState(history.state, "", url);
}

export function periodLabel(period) {
  return (PERIODS.find((p) => p.value === (period || "")) || PERIODS[0]).label.toLowerCase();
}

/**
 * Renders labelled <select>s into `container`.
 * @param {{provider?: boolean, onChange: (filters) => void}} options
 */
export function createFilters(container, { provider = true, onChange }) {
  const state = readFilters();
  if (!provider) state.provider = "";
  let idCount = 0;
  const field = (label, select) => {
    const id = `filter-${Date.now().toString(36)}-${idCount++}`;
    select.id = id;
    return h("div", { class: "filter" }, h("label", { class: "filter__label", for: id }, label), select);
  };

  const periodSelect = h("select", { class: "filter__select" },
    PERIODS.map((p) => h("option", { value: p.value, selected: p.value === state.period }, p.label)));
  periodSelect.addEventListener("change", () => update({ period: periodSelect.value }));
  const fields = [field("Time period", periodSelect)];

  let providerSelect = null;
  if (provider) {
    providerSelect = h("select", { class: "filter__select" },
      h("option", { value: "" }, "All providers"),
      h("option", { value: "unidentified", selected: state.provider === "unidentified" }, "Provider not identified"));
    providerSelect.addEventListener("change", () => update({ provider: providerSelect.value }));
    fields.push(field("Provider", providerSelect));
    loadProviders().then((list) => {
      const anchor = providerSelect.options[1];
      for (const p of list) {
        providerSelect.insertBefore(h("option", { value: p.slug, selected: p.slug === state.provider }, p.name), anchor);
      }
    });
  }

  container.append(h("div", { class: "filters" }, fields));

  function update(change) {
    Object.assign(state, change);
    writeFilters(state);
    onChange({ ...state });
  }

  return { get: () => ({ ...state }) };
}
