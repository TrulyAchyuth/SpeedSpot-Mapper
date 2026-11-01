// Accessible place search (WAI-ARIA combobox pattern). Searches our own region list
// on the server; no third-party geocoder sees what people type.
import { api } from "./api.js";
import { debounce, h, icon } from "./dom.js";

let pickerCount = 0;

export function createAreaPicker(container, { onSelect, placeholder = "Search a state, district or city", onFocus } = {}) {
  const id = `area-picker-${++pickerCount}`;
  let results = [];
  let active = -1;

  const input = h("input", {
    id: `${id}-input`, class: "search-field__input", type: "search", autocomplete: "off", spellcheck: "false",
    placeholder, role: "combobox", "aria-autocomplete": "list", "aria-expanded": "false",
    "aria-controls": `${id}-list`,
  });
  const list = h("ul", { id: `${id}-list`, class: "search-results", role: "listbox", "aria-label": "Places", hidden: true });
  const status = h("span", { class: "visually-hidden", role: "status", "aria-live": "polite" });

  container.append(
    h("label", { class: "visually-hidden", for: input.id }, "Search for a place in India"),
    h("div", { class: "search-field" }, icon("search"), input),
    list, status,
  );

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  }

  function highlight(index) {
    active = index;
    [...list.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === index)));
    if (index >= 0) input.setAttribute("aria-activedescendant", `${id}-opt-${index}`);
  }

  function render() {
    list.replaceChildren(...results.map((place, i) => h("li", {
      id: `${id}-opt-${i}`, role: "option", class: "search-result", "aria-selected": "false",
      onMousedown: (e) => { e.preventDefault(); choose(i); },
    }, h("span", { class: "search-result__name" }, place.name), h("span", { class: "search-result__label" }, place.label))));
    if (!results.length && input.value.trim().length >= 2) {
      list.append(h("li", { class: "search-result search-result--empty", role: "presentation" }, "No matching places in India"));
    }
    list.hidden = input.value.trim().length < 2;
    input.setAttribute("aria-expanded", String(!list.hidden));
    status.textContent = input.value.trim().length >= 2 ? `${results.length} places found` : "";
  }

  function choose(index) {
    const place = results[index];
    if (!place) return;
    input.value = place.name;
    close();
    onSelect?.(place);
  }

  const search = debounce(async () => {
    const q = input.value.trim();
    if (q.length < 2) {
      results = [];
      render();
      return;
    }
    try {
      const found = await api.search(q);
      if (input.value.trim() !== q) return; // a newer query is in flight
      results = found;
    } catch {
      results = [];
    }
    render();
  }, 180);

  input.addEventListener("input", search);
  input.addEventListener("focus", () => onFocus?.());
  input.addEventListener("blur", () => setTimeout(close, 100));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" && results.length) {
      e.preventDefault();
      if (list.hidden) render();
      highlight((active + 1) % results.length);
    } else if (e.key === "ArrowUp" && results.length) {
      e.preventDefault();
      highlight((active - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(active >= 0 ? active : 0);
    } else if (e.key === "Escape") {
      close();
    }
  });

  return {
    input,
    setValue(text) { input.value = text || ""; },
  };
}
