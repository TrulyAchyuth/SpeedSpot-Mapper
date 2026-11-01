// Explore India: India → state → district → city → neighbourhood (~1 km) → block (~150 m).
//
// Colouring rules (honesty first):
//  - An area is filled Good/Fair/Weak only when the server says it has enough tests,
//    spread over enough neighbourhoods/districts (services/stats.py). Otherwise it is neutral:
//    "Not enough tests" (some data) is visibly different from "No tests yet".
//  - "Colour by: Tests" shows measurement density instead of quality.
//  - Street tiles appear only from district zoom; the national view is our own
//    LGD boundaries on a plain background.
import { api, statsFor } from "../api.js";
import { createAreaPicker } from "../area-picker.js";
import { areaSummary, errorMessage, loading, providerRows, scoreBadge, stateMessage } from "../components.js";
import { debounce, getAreaParam, h, icon, prefersReducedMotion, replace, setAreaParam } from "../dom.js";
import * as fmt from "../format.js";
import { createFilters, periodLabel, readFilters } from "../filters.js";
import { encode } from "../geohash.js";
import { requestLocation } from "../location.js";
import * as nav from "../navigate.js";

const L = window.L;
const INDIA_BOUNDS = [[6.5, 68.0], [37.5, 97.5]];
const TILE_MIN_ZOOM = 8;
const CELL_MIN_ZOOM = 10;
const BLOCK_MIN_ZOOM = 13;
const DESKTOP = window.matchMedia("(min-width: 768px)");

const css = getComputedStyle(document.documentElement);
const token = (name) => css.getPropertyValue(name).trim();
const COLOR = {
  good: token("--score-good-fill"), fair: token("--score-fair-fill"), weak: token("--score-weak-fill"),
  insufficient: token("--map-insufficient"), none: token("--map-land"), boundary: token("--map-boundary"),
  selected: token("--color-forest"),
  density: [token("--density-1"), token("--density-2"), token("--density-3")],
};
// Sample-count thresholds for "Colour by: Tests": regions vs. grid cells.
const DENSITY_STEPS = { region: [1, 20, 100], cell: [1, 5, 20] };

const state = {
  selected: null,        // current area code (region code or geohash)
  stateCode: null,       // state whose districts are drawn
  districtCode: null,
  stats: new Map(),      // code -> summary, for states and districts
  districtGeo: new Map(),
  cellRequest: 0,
  highlightedCell: null,
  filters: readFilters(),
  colourBy: "score",     // "score" | "density"
  position: null,        // exact position, kept on this device only (guided navigation)
};

// ---------- Map setup ----------
const map = L.map("map", {
  zoomControl: false, minZoom: 4, maxZoom: 17, zoomSnap: 0.5,
  maxBounds: [[-2, 58], [42, 106]], maxBoundsViscosity: 0.8,
});
map.attributionControl.setPrefix(false);
map.attributionControl.addAttribution("Boundaries: LGD, Government of India");

// OpenStreetMap's own tiles: free for light use under the OSM Tile Usage Policy, with
// attribution. Softened to greyscale in map.css. A production launch needs its own tile host.
const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
});
map.createPane("regions").style.zIndex = 410;
map.createPane("cells").style.zIndex = 420;

const statesLayer = L.geoJSON(null, { pane: "regions", style: regionStyle("state"), onEachFeature: bindRegion });
const districtsLayer = L.geoJSON(null, { pane: "regions", style: regionStyle("district"), onEachFeature: bindRegion });
const cellsLayer = L.layerGroup([], { pane: "cells" }).addTo(map);
const youLayer = L.layerGroup().addTo(map);
const navLayer = L.layerGroup().addTo(map);
statesLayer.addTo(map);
districtsLayer.addTo(map);

function densityColour(count, kind) {
  const steps = DENSITY_STEPS[kind];
  if (!count) return null;
  return count >= steps[2] ? COLOR.density[2] : count >= steps[1] ? COLOR.density[1] : COLOR.density[0];
}

function fillFor(summary) {
  if (state.colourBy === "density") {
    const colour = densityColour(summary?.sample_count, "region");
    return colour ? { color: colour, opacity: 0.8 } : { color: COLOR.none, opacity: 0.9 };
  }
  if (summary?.status === "ok") return { color: COLOR[summary.band], opacity: 0.62 };
  if (summary?.status === "insufficient") return { color: COLOR.insufficient, opacity: 0.9 };
  return { color: COLOR.none, opacity: 0.9 };
}

function regionStyle(level) {
  return (feature) => {
    const code = feature.properties.code;
    const zoom = map.getZoom();
    const fill = fillFor(state.stats.get(code));
    const style = { color: COLOR.boundary, weight: level === "state" ? 0.9 : 0.6, fillColor: fill.color, fillOpacity: fill.opacity };

    if (level === "state") {
      if (code === state.stateCode) style.fillOpacity = 0;             // its districts are drawn instead
      else if (state.stateCode) style.fillOpacity *= 0.45;             // fade other states
      if (zoom >= TILE_MIN_ZOOM) style.fillOpacity = 0;
    } else {
      if (zoom >= CELL_MIN_ZOOM) style.fillOpacity = 0;                // neighbourhood cells take over
      else if (zoom >= TILE_MIN_ZOOM) style.fillOpacity *= 0.55;
      if (code === state.districtCode) Object.assign(style, { color: COLOR.selected, weight: 2.2 });
    }
    if (level === "state" && code === state.stateCode) Object.assign(style, { color: COLOR.selected, weight: 1.6 });
    return style;
  };
}

function tooltipFor(name, summary) {
  const tests = summary?.sample_count ? ` · ${fmt.plural(summary.sample_count, "test")}` : "";
  const status = summary?.status === "ok"
    ? `${fmt.BAND_LABEL[summary.band]} · ${summary.score}/100${tests}`
    : summary?.status === "insufficient" ? `Not enough tests yet${tests}` : "No tests yet";
  return h("div", { class: "map-tooltip" }, h("strong", {}, name), h("span", {}, status));
}

function bindRegion(feature, layer) {
  const { code, name } = feature.properties;
  layer.bindTooltip(() => tooltipFor(name, state.stats.get(code)), { sticky: true, direction: "top", opacity: 1 });
  layer.on({
    click: () => selectArea(code),
    mouseover: () => layer.setStyle({ weight: 2, color: COLOR.selected }),
    mouseout: () => (code.split("-").length === 2 ? statesLayer : districtsLayer).resetStyle(layer),
  });
}

function restyle() {
  statesLayer.setStyle(regionStyle("state"));
  districtsLayer.setStyle(regionStyle("district"));
}

// ---------- Panel ----------
const panel = document.getElementById("panel");
const panelBody = document.getElementById("panel-body");
const breadcrumbEl = document.getElementById("breadcrumb");
const sheetToggle = document.getElementById("sheet-toggle");
const toast = document.getElementById("map-toast");

function setSheet(mode) {
  panel.dataset.sheet = mode;
  sheetToggle.setAttribute("aria-expanded", String(mode === "open"));
  sheetToggle.querySelector(".visually-hidden").textContent = mode === "open" ? "Show less" : "Show more details";
}
sheetToggle.addEventListener("click", () => setSheet(panel.dataset.sheet === "open" ? "peek" : "open"));

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => (toast.hidden = true), 4000);
}

function renderBreadcrumb(trail) {
  const back = trail.length > 1 && h("button", { type: "button", class: "back-chip", onClick: () => selectArea("IN", { focus: true }) },
    icon("arrow-left", "sm"), "All of India");
  replace(breadcrumbEl, back || "", h("ol", {}, trail.map((item, i) => h("li", {},
    i < trail.length - 1
      ? h("button", { type: "button", class: "breadcrumb__link", onClick: () => selectArea(item.code, { focus: true }) }, item.name)
      : h("span", { "aria-current": "location" }, item.name)))));
}

function regionList(title, children, { collapseEmpty = true } = {}) {
  const scored = children.filter((c) => c.summary.status === "ok").sort((a, b) => b.summary.score - a.summary.score);
  const some = children.filter((c) => c.summary.status === "insufficient").sort((a, b) => b.summary.sample_count - a.summary.sample_count);
  const none = children.filter((c) => c.summary.status === "no_data");
  const item = (c) => h("li", {}, h("button", { type: "button", class: "region-item", onClick: () => selectArea(c.code, { focus: true }) },
    h("span", { class: "region-item__text" },
      h("span", { class: "region-item__name" }, c.name),
      h("span", { class: "region-item__meta" }, c.summary.sample_count ? fmt.plural(c.summary.sample_count, "test") : "No tests yet")),
    c.summary.status === "ok" ? h("span", { class: "region-item__score" }, String(c.summary.score)) : null,
    scoreBadge(c.summary.band, c.summary.status),
    icon("chevron-right", "sm")));

  const lists = [];
  if (scored.length) lists.push(h("ul", { class: "region-list" }, scored.map(item)));
  if (some.length) lists.push(h("p", { class: "region-list__label" }, "Not enough tests yet"), h("ul", { class: "region-list" }, some.map(item)));
  if (none.length) {
    const noneList = h("ul", { class: "region-list" }, none.map(item));
    lists.push(collapseEmpty
      ? h("details", { class: "region-list__more" }, h("summary", {}, `${fmt.plural(none.length, "place")} with no tests yet`), noneList)
      : noneList);
  }
  return h("section", { class: "panel-section", "aria-label": title }, h("h3", { class: "panel-section__title" }, title), lists);
}

function providersSection(data) {
  const rows = providerRows(data.providers, { limit: 3 });
  return h("section", { class: "panel-section" },
    h("h3", { class: "panel-section__title" }, "Top providers here"),
    rows || h("p", { class: "muted small" }, data.providers.insufficient.length
      ? `Not enough tests per provider yet (${data.providers.min_samples} needed for each).`
      : "No provider information here yet."),
    h("a", { class: "text-link", href: `/providers?area=${encodeURIComponent(data.area.code)}` }, "Compare all providers", icon("arrow-right", "sm")));
}

function renderPanel(data) {
  const { area } = data;
  const heading = h("h2", { class: "panel-title", tabindex: "-1" }, area.level === "country" ? "India" : area.name);
  const children = data.children || [];
  const childTitle = { country: "States and union territories", state: "Districts", district: "Cities and towns with tests" }[area.level];

  replace(panelBody,
    h("p", { class: "eyebrow" }, area.level === "country" ? "All of India" : area.label),
    heading,
    areaSummary(data),
    childTitle && (children.length
      ? regionList(childTitle, children)
      : h("section", { class: "panel-section" }, h("h3", { class: "panel-section__title" }, childTitle),
          h("p", { class: "muted small" }, "No cities or towns with tests yet."))),
    (area.level === "city" || area.level === "district") && h("button", {
      type: "button", class: "button button--secondary button--block",
      onClick: () => map.flyTo(map.getCenter(), Math.max(map.getZoom(), CELL_MIN_ZOOM + 1), { animate: !prefersReducedMotion() }),
    }, icon("layers"), "Show neighbourhoods"),
    providersSection(data),
    h("a", { class: "text-link", href: `/insights?area=${encodeURIComponent(area.code)}` }, "See neighbourhood insights", icon("arrow-right", "sm")),
  );
  return heading;
}

// ---------- Data loading ----------
async function loadStatesGeo() {
  const response = await fetch("/static/geo/states.geojson");
  statesLayer.addData(await response.json());
}

async function ensureDistricts(stateCode) {
  if (state.stateCode === stateCode) return;
  state.stateCode = stateCode;
  districtsLayer.clearLayers();
  if (!stateCode) return;
  let geo = state.districtGeo.get(stateCode);
  if (!geo) {
    geo = await (await fetch(`/static/geo/districts/${stateCode}.geojson`)).json();
    state.districtGeo.set(stateCode, geo);
  }
  if (state.stateCode === stateCode) districtsLayer.addData(geo);
}

function rememberChildren(children) {
  for (const child of children || []) state.stats.set(child.code, child.summary);
}

function fitTo(bbox, maxZoom) {
  const bounds = L.latLngBounds([bbox[0], bbox[1]], [bbox[2], bbox[3]]);
  const padding = DESKTOP.matches
    ? { paddingTopLeft: [panel.offsetWidth + 40, 24], paddingBottomRight: [72, 24] }
    : { paddingTopLeft: [16, 16], paddingBottomRight: [16, Math.min(panel.offsetHeight, window.innerHeight * 0.45) + 16] };
  map.flyToBounds(bounds, { ...padding, maxZoom, duration: 0.8, animate: !prefersReducedMotion() });
}

// ---------- Selection ----------
let selectionToken = 0;

async function selectArea(code, { push = true, fit = true, focus = false } = {}) {
  const myToken = ++selectionToken;
  state.selected = code;
  if (push) setAreaParam(code);
  replace(panelBody, loading(5));

  let data;
  try {
    data = await statsFor(code, state.filters);
  } catch (error) {
    if (myToken !== selectionToken) return;
    if (error.status === 404 || error.status === 400) {
      replace(panelBody, stateMessage({
        iconName: "pin", title: "We couldn't find that place", text: error.message,
        action: h("button", { type: "button", class: "button button--secondary", onClick: () => selectArea("IN") }, icon("globe"), "Back to all of India"),
      }));
    } else {
      replace(panelBody, errorMessage(error, () => selectArea(code, { push: false })));
    }
    return;
  }
  if (myToken !== selectionToken) return; // a newer selection won

  const { area } = data;
  const trail = area.breadcrumb.length ? area.breadcrumb.map((r) => ({ code: r.code, name: r.name })) : [{ code: "IN", name: "India" }];
  if (area.level === "neighbourhood" || area.level === "block") trail.push({ code: area.code, name: area.name });
  renderBreadcrumb(trail);

  const stateCode = trail[1]?.code ?? null;
  const districtCode = ["district", "city", "neighbourhood", "block"].includes(area.level) ? trail[2]?.code ?? null : null;

  if (area.level === "country") rememberChildren(data.children);
  if (area.level === "state") rememberChildren(data.children);
  if (stateCode && area.level !== "state" && !state.stats.has(`${stateCode}-loaded`)) {
    try {
      rememberChildren((await api.regionStats(stateCode, state.filters)).children);
      state.stats.set(`${stateCode}-loaded`, true);
    } catch { /* districts stay neutral; the panel still works */ }
  }
  if (area.level === "state") state.stats.set(`${stateCode}-loaded`, true);

  await ensureDistricts(stateCode);
  state.districtCode = districtCode;
  restyle();
  highlightCell(area.level === "neighbourhood" || area.level === "block" ? area.code : null);

  const heading = renderPanel(data);
  if (focus) heading.focus({ preventScroll: true });
  if (fit && area.bbox) {
    const maxZoom = { country: 5, state: 8, district: 10, city: 12, neighbourhood: 13, block: 15 }[area.level];
    fitTo(area.level === "country" ? [6.5, 68.0, 37.1, 97.4] : area.bbox, maxZoom);
  }
  document.title = `${area.level === "country" ? "Explore India" : area.name} · SpeedSpot Mapper`;
}

// ---------- Neighbourhood / block cells ----------
function highlightCell(code) {
  state.highlightedCell = code;
  cellsLayer.eachLayer((layer) => layer.setStyle(cellStyle(layer.feature)));
}

function cellStyle(cell) {
  const selected = state.highlightedCell === cell.cell_id;
  const base = state.colourBy === "density"
    ? { fillColor: densityColour(cell.sample_count, "cell"), fillOpacity: 0.75, color: "#ffffff", weight: 1, dashArray: null }
    : cell.status === "ok"
    ? { fillColor: COLOR[cell.band], fillOpacity: 0.6, color: "#ffffff", weight: 1, dashArray: null }
    : { fillColor: COLOR.insufficient, fillOpacity: 0.35, color: token("--map-insufficient-stroke"), weight: 1, dashArray: "3 3" };
  return selected ? { ...base, color: COLOR.selected, weight: 2.5, dashArray: null } : base;
}

const loadCells = debounce(async () => {
  const zoom = map.getZoom();
  const request = ++state.cellRequest;
  if (zoom < CELL_MIN_ZOOM) {
    cellsLayer.clearLayers();
    return;
  }
  const precision = zoom >= BLOCK_MIN_ZOOM ? 7 : 6;
  const b = map.getBounds().pad(0.1);
  const bbox = [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()].map((v) => Number(v.toFixed(5)));
  try {
    const cells = await api.cells(bbox, precision, state.filters);
    if (request !== state.cellRequest) return;
    cellsLayer.clearLayers();
    for (const cell of cells) {
      const [s, w, n, e] = cell.bounds;
      const rect = L.rectangle([[s, w], [n, e]], { pane: "cells", ...cellStyle(cell) });
      rect.feature = cell;
      const label = precision === 7 ? "Block (~150 m)" : "Neighbourhood (~1 km)";
      const status = cell.status === "ok"
        ? `${fmt.BAND_LABEL[cell.band]} · ${cell.score}/100 · ${fmt.plural(cell.sample_count, "test")}`
        : `Not enough tests yet (${cell.sample_count} of 5)`;
      rect.bindTooltip(() => h("div", { class: "map-tooltip" }, h("strong", {}, label), h("span", {}, status)), { sticky: true, opacity: 1 });
      rect.on("click", () => selectArea(cell.cell_id, { fit: false }));
      cellsLayer.addLayer(rect);
    }
  } catch (error) {
    if (request === state.cellRequest && error.code !== "area_too_large") showToast(error.message);
  }
}, 250);

function syncZoomLayers() {
  const zoom = map.getZoom();
  if (zoom >= TILE_MIN_ZOOM && !map.hasLayer(tiles)) tiles.addTo(map);
  if (zoom < TILE_MIN_ZOOM && map.hasLayer(tiles)) map.removeLayer(tiles);
  document.getElementById("explore").dataset.detail = zoom >= CELL_MIN_ZOOM ? "cells" : "regions";
  restyle();
  loadCells();
}
map.on("zoomend", syncZoomLayers);
map.on("moveend", loadCells);

// ---------- Filters, colour mode and legend ----------
const legendEl = document.getElementById("legend");

function renderLegend() {
  const item = (cls, label) => h("span", { class: "legend-item" }, h("span", { class: `legend-swatch legend-swatch--${cls}` }), label);
  replace(legendEl, ...(state.colourBy === "density"
    ? [item("density-1", "Few tests"), item("density-2", "Some"), item("density-3", "Many"), item("none", "No tests yet")]
    : [item("good", "Good"), item("fair", "Fair"), item("weak", "Weak"), item("insufficient", "Not enough tests"), item("none", "No tests yet")]));
}

function reloadForFilters() {
  state.stats.clear();          // child summaries depend on the filters
  if (state.selected) selectArea(state.selected, { push: false, fit: false });
  loadCells();
}

createFilters(document.getElementById("map-filters"), {
  onChange: (filters) => {
    state.filters = filters;
    reloadForFilters();
  },
});

document.getElementById("colour-by").addEventListener("change", (event) => {
  state.colourBy = event.target.value;
  renderLegend();
  restyle();
  cellsLayer.eachLayer((layer) => layer.setStyle(cellStyle(layer.feature)));
});

// ---------- Guided navigation ----------
const navSection = document.getElementById("nav-section");
const NAV_RADII = [1500, 3000];

function navIntro() {
  replace(navSection,
    h("button", { type: "button", class: "button button--primary button--block", onClick: () => findBetter(NAV_RADII[0]) },
      icon("route"), "Find a better connection nearby"));
}

function clearNavigation() {
  navLayer.clearLayers();
  map.attributionControl.removeAttribution(nav.ROUTING_ATTRIBUTION);
  navIntro();
}

function destinationLabel(d) {
  return d.level === "block" ? "Block (~150 m)" : "Neighbourhood (~1 km)";
}

async function showRoute(d, item, button) {
  button.disabled = true;
  const status = item.querySelector(".nav-item__route");
  status.textContent = "Finding a walking route…";
  navLayer.eachLayer((layer) => { if (layer.options.className === "nav-route") navLayer.removeLayer(layer); });
  try {
    const route = await nav.walkingRoute([state.position.lat, state.position.lng], d.center);
    L.polyline(route.latlngs, { color: COLOR.selected, weight: 4, opacity: 0.85, className: "nav-route", interactive: false }).addTo(navLayer);
    map.attributionControl.addAttribution(nav.ROUTING_ATTRIBUTION);
    status.textContent = `Walking route: ${nav.formatDistance(route.distance_m)} · about ${nav.formatMinutes(route.duration_min)}`;
    map.flyToBounds(L.latLngBounds(route.latlngs), { padding: [60, 60], animate: !prefersReducedMotion() });
  } catch (error) {
    L.polyline([[state.position.lat, state.position.lng], d.center], { color: COLOR.selected, weight: 2, dashArray: "6 6", className: "nav-route", interactive: false }).addTo(navLayer);
    status.textContent = `${error.message} The dashed line shows the direction only.`;
  } finally {
    button.disabled = false;
  }
}

function navItem(d, index) {
  const straight = nav.haversineM([state.position.lat, state.position.lng], d.center);
  const item = h("li", { class: "nav-item" });
  const routeButton = h("button", { type: "button", class: "button button--secondary" }, icon("route"), "Show walking route");
  routeButton.addEventListener("click", () => showRoute(d, item, routeButton));
  item.append(
    h("div", { class: "nav-item__head" },
      h("span", { class: "nav-item__number", "aria-hidden": "true" }, String(index + 1)),
      h("div", { class: "nav-item__text" },
        h("strong", {}, `${destinationLabel(d)} · ${d.score}/100`),
        h("span", { class: "muted small" },
          `About ${nav.formatDistance(straight)} away · roughly ${nav.formatMinutes(nav.estimateWalkMinutes(straight))} on foot`)),
      fmt.BAND_LABEL[d.band] && h("span", { class: `score-badge score-badge--${d.band}` }, fmt.BAND_LABEL[d.band])),
    h("p", { class: "muted small nav-item__meta" },
      `Based on ${fmt.plural(d.sample_count, "test")}, latest ${fmt.timeAgo(d.last_updated)}`),
    h("p", { class: "small nav-item__route", role: "status" }),
    h("div", { class: "button-row" }, routeButton,
      h("a", { class: "button button--ghost", href: nav.googleMapsUrl(d.center), target: "_blank", rel: "noopener" }, "Open in Google Maps")));
  return item;
}

async function findBetter(radius) {
  replace(navSection, loading(3));
  try {
    if (!state.position) {
      const pos = await requestLocation("We'll look for places near you where people have measured a stronger connection.");
      state.position = pos;
    }
    // Only the ~150 m area code is sent to SpeedSpot; the exact position stays on this device.
    const result = await api.nearby(encode(state.position.lat, state.position.lng, 7), radius, state.filters);
    navLayer.clearLayers();
    L.circleMarker([state.position.lat, state.position.lng], { radius: 7, color: "#ffffff", weight: 2, fillColor: COLOR.selected, fillOpacity: 1, interactive: false }).addTo(navLayer);

    const header = [
      h("div", { class: "nav-header" }, h("h3", { class: "panel-section__title" }, "Better connection nearby"),
        h("button", { type: "button", class: "text-button", onClick: clearNavigation }, icon("close", "sm"), "Close")),
      h("p", { class: "coverage-note" }, icon("info", "sm"), result.notice),
    ];
    if (!result.destinations.length) {
      replace(navSection, ...header, h("p", { class: "muted" },
        "We don't have enough recent measurements nearby to recommend a better-connected area.",
        h("span", { class: "small" }, ` (Searched within ${nav.formatDistance(radius)}, ${periodLabel(state.filters.period)}.)`)),
        radius < NAV_RADII[1] && h("button", { type: "button", class: "button button--secondary button--block", onClick: () => findBetter(NAV_RADII[1]) },
          `Search up to ${nav.formatDistance(NAV_RADII[1])}`));
      map.flyTo([state.position.lat, state.position.lng], 14, { animate: !prefersReducedMotion() });
      return;
    }
    const points = [[state.position.lat, state.position.lng]];
    result.destinations.forEach((d, i) => {
      points.push(d.center);
      L.marker(d.center, {
        icon: L.divIcon({ className: "nav-marker", html: `<span>${i + 1}</span>`, iconSize: [30, 30] }),
        keyboard: false, title: `${destinationLabel(d)} · ${d.score}/100`,
      }).addTo(navLayer);
    });
    replace(navSection, ...header,
      h("p", { class: "muted small" }, "Walking routes are calculated by the OpenStreetMap routing service (FOSSGIS), which receives your start and end points and keeps them in its server logs. Google Maps receives the destination."),
      h("ol", { class: "nav-list" }, result.destinations.map(navItem)));
    map.flyToBounds(L.latLngBounds(points), { padding: [60, 60], maxZoom: 16, animate: !prefersReducedMotion() });
  } catch (error) {
    if (["cancelled", "denied"].includes(error.code)) navIntro();
    else replace(navSection, errorMessage(error, () => findBetter(radius)));
  }
}

// ---------- Controls ----------
document.getElementById("zoom-in").addEventListener("click", () => map.zoomIn());
document.getElementById("zoom-out").addEventListener("click", () => map.zoomOut());
document.getElementById("reset-view").addEventListener("click", () => selectArea("IN", { focus: true }));
document.getElementById("locate-me").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const pos = await requestLocation("We'll zoom the map to the area around you.");
    state.position = pos;
    youLayer.clearLayers();
    // Drawn on this device only; nothing about the exact position is sent anywhere.
    L.circle([pos.lat, pos.lng], { radius: Math.min(pos.accuracy, 1500), color: COLOR.selected, weight: 1, fillOpacity: 0.08, interactive: false }).addTo(youLayer);
    L.circleMarker([pos.lat, pos.lng], { radius: 6, color: "#ffffff", weight: 2, fillColor: COLOR.selected, fillOpacity: 1, interactive: false }).addTo(youLayer);
    await selectArea(encode(pos.lat, pos.lng, 6), { fit: false });
    map.flyTo([pos.lat, pos.lng], 13, { animate: !prefersReducedMotion() });
  } catch (error) {
    if (!["cancelled", "denied"].includes(error.code)) showToast(error.message);
  } finally {
    button.disabled = false;
  }
});

createAreaPicker(document.getElementById("map-search"), {
  onSelect: (place) => {
    selectArea(place.code, { focus: true });
    if (!DESKTOP.matches) setSheet("peek");
  },
  onFocus: () => { if (!DESKTOP.matches) setSheet("open"); },
});

window.addEventListener("popstate", () => selectArea(getAreaParam() || "IN", { push: false }));

// ---------- Start ----------
window.addEventListener("speedspot:layout", () => setTimeout(() => map.invalidateSize(), 260)); // sidebar resized
renderLegend();
navIntro();
map.fitBounds(INDIA_BOUNDS, { animate: false });
syncZoomLayers();
loadStatesGeo()
  .then(() => selectArea(getAreaParam() || "IN", { push: false }))
  .then(() => {
    // Arriving from the home page's "Find a better connection nearby" shortcut.
    if (new URLSearchParams(window.location.search).get("nearby") === "1") findBetter(NAV_RADII[0]);
  })
  .catch(() => replace(panelBody, errorMessage({ message: "The map couldn't load. Please refresh the page." }, () => location.reload())));
