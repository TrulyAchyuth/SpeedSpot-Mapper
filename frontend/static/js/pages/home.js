// Home: real national numbers, an interactive state map, and facts only where data supports them.
import { api } from "../api.js";
import { createAreaPicker } from "../area-picker.js";
import { distributionBar, emptyIllustration, scoreBadge, testCta } from "../components.js";
import { h, icon, replace } from "../dom.js";
import * as fmt from "../format.js";

const L = window.L;
const overview = document.getElementById("overview");
const availability = document.getElementById("availability");

function stat(label, value, hint, extra = null, iconName = null) {
  return h("div", { class: "stat-tile" },
    h("span", { class: "stat-tile__label" }, iconName && icon(iconName, "sm"), label),
    h("strong", { class: "stat-tile__value" }, value),
    extra,
    hint && h("span", { class: "stat-tile__hint" }, hint));
}

function renderOverview(data, states) {
  const s = data.summary;
  const scoredStates = states.filter((st) => st.summary.status === "ok").length;
  if (!s.sample_count) {
    replace(overview,
      stat("Tests shared", "0", "Be the first to add one.", null, "users"),
      stat("Connection score", "–", "Appears once enough people test.", null, "gauge"),
      stat("Areas with enough data", "0", "Neighbourhoods need 5 tests each.", null, "map"),
      stat("Latest test", "–", "No tests yet.", null, "clock"));
    replace(availability, emptyIllustration("Help map India's connectivity",
      "Run your first speed test and contribute an anonymised measurement.", testCta("Start a speed test")));
    return;
  }
  replace(overview,
    stat("Connection score", s.status === "ok" ? `${s.score}/100` : "–",
      s.status === "ok" ? "Median of all tests in India" : "Not enough spread across India yet",
      scoreBadge(s.band, s.status), "gauge"),
    stat("Tests shared", fmt.number(s.sample_count), "Genuine community measurements", null, "users"),
    stat("Areas with enough data", fmt.number(data.coverage.neighbourhoods_with_score),
      `of ${fmt.plural(data.coverage.neighbourhoods_tested, "neighbourhood")} tested`, null, "map"),
    stat("Latest test", fmt.timeAgo(s.last_updated) || "–", `Across ${fmt.plural(data.coverage.districts_tested, "district")}`, null, "clock"));

  const pct = Math.round((scoredStates / 36) * 100);
  const bar = h("span", { class: "availability__fill" });
  bar.style.width = `${Math.max(pct, 2)}%`;
  replace(availability,
    h("div", { class: "availability__text" },
      h("strong", {}, "Data availability"),
      h("span", { class: "muted" }, `${scoredStates} of 36 states and union territories have enough tests for a score.`)),
    h("span", { class: "availability__bar", role: "img", "aria-label": `${scoredStates} of 36 states have a score` }, bar));
}

function renderStates(states) {
  const scored = states.filter((s) => s.summary.status === "ok").sort((a, b) => b.summary.score - a.summary.score);
  const target = document.getElementById("home-states");
  if (!scored.length) {
    replace(target, h("p", { class: "muted small" }, "No state has enough tests for a score yet. Every shared test helps."));
    return;
  }
  replace(target, h("ul", { class: "mini-list" }, scored.slice(0, 4).map((s) => h("li", {},
    h("a", { href: `/map?area=${s.code}` },
      h("span", { class: "mini-list__name" }, s.name),
      h("span", { class: "mini-list__score" }, String(s.summary.score)),
      scoreBadge(s.summary.band))))));
}

function renderFacts(data, states) {
  const facts = [];
  const scored = states.filter((s) => s.summary.status === "ok");
  if (scored.length) {
    const best = scored.reduce((a, b) => (b.summary.score > a.summary.score ? b : a));
    facts.push([icon("trophy", "sm"), `Best-connected state with enough data: `, h("strong", {}, best.name),
      ` (${best.summary.score}/100, ${fmt.plural(best.summary.sample_count, "test")})`]);
  }
  const tested = states.filter((s) => s.summary.sample_count);
  if (tested.length) {
    const busiest = tested.reduce((a, b) => (b.summary.sample_count > a.summary.sample_count ? b : a));
    facts.push([icon("users", "sm"), "Most tested: ", h("strong", {}, busiest.name), ` (${fmt.plural(busiest.summary.sample_count, "test")})`]);
    const waiting = tested.filter((s) => s.summary.status !== "ok").length;
    if (waiting) facts.push([icon("info", "sm"), `${waiting} more ${waiting === 1 ? "state has" : "states have"} some tests but not enough for a fair score yet.`]);
  }
  if (data.providers.ranked) {
    facts.push([icon("compare", "sm"), `${fmt.plural(data.providers.ranked, "provider")} can be compared nationally (5+ tests each).`]);
  }
  const list = document.getElementById("home-facts");
  if (!facts.length) {
    replace(list, h("li", { class: "muted" }, "Facts will appear here once people start sharing tests."));
    return;
  }
  replace(list, ...facts.map((parts) => h("li", {}, ...parts)));
}

function renderMap(states) {
  const el = document.getElementById("home-map");
  const map = L.map(el, { zoomControl: false, attributionControl: true, scrollWheelZoom: false, dragging: !L.Browser.mobile,
    minZoom: 3.5, maxZoom: 6, zoomSnap: 0.25 });
  map.attributionControl.setPrefix(false);
  map.attributionControl.addAttribution("Boundaries: LGD, Government of India");
  const css = getComputedStyle(document.documentElement);
  const colour = (s) => s?.status === "ok" ? css.getPropertyValue(`--score-${s.band}-fill`).trim()
    : s?.status === "insufficient" ? css.getPropertyValue("--map-insufficient").trim() : css.getPropertyValue("--map-land").trim();
  const byCode = new Map(states.map((s) => [s.code, s.summary]));

  fetch("/static/geo/states.geojson").then((r) => r.json()).then((geo) => {
    const layer = L.geoJSON(geo, {
      style: (f) => ({ color: css.getPropertyValue("--map-boundary").trim(), weight: 0.8, fillOpacity: byCode.get(f.properties.code)?.status === "ok" ? 0.7 : 0.95, fillColor: colour(byCode.get(f.properties.code)) }),
      onEachFeature: (f, l) => {
        const s = byCode.get(f.properties.code);
        const status = s?.status === "ok" ? `${fmt.BAND_LABEL[s.band]} · ${s.score}/100` : s?.status === "insufficient" ? "Not enough tests yet" : "No tests yet";
        l.bindTooltip(() => h("div", { class: "map-tooltip" }, h("strong", {}, f.properties.name), h("span", {}, status)), { sticky: true, opacity: 1 });
        l.on("click", () => { window.location.href = `/map?area=${f.properties.code}`; });
      },
    }).addTo(map);
    map.fitBounds(layer.getBounds(), { padding: [8, 8] });
  });
  window.addEventListener("speedspot:layout", () => setTimeout(() => map.invalidateSize(), 260));
}

createAreaPicker(document.getElementById("home-search"), {
  onSelect: (place) => { window.location.href = `/map?area=${encodeURIComponent(place.code)}`; },
});

Promise.all([api.statistics("IN"), api.mapStates()]).then(([data, states]) => {
  renderOverview(data, states);
  renderStates(states);
  renderFacts(data, states);
  replace(document.getElementById("home-distribution"),
    data.coverage.neighbourhoods_tested ? distributionBar(data.neighbourhood_distribution)
      : h("p", { class: "muted" }, "No neighbourhoods have been tested yet."));
  renderMap(states);
}).catch(() => {
  replace(overview, h("p", { class: "muted" }, "Live numbers are unavailable right now. Please try again shortly."));
  renderMap([]);
});
