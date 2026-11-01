// Neighbourhood insights, in a fixed order: context → overview → distribution → over time →
// density → providers → weak areas → sub-area comparison → CSV. Every section reflects the
// chosen area, time period and provider, and shows an honest empty state when data is thin.
import { api, exportUrl } from "../api.js";
import { createAreaBar } from "../area-bar.js";
import { barFill, distributionBar, emptyIllustration, errorMessage, loading, scoreBadge, testCta } from "../components.js";
import { getAreaParam, h, icon, replace, setAreaParam } from "../dom.js";
import { createFilters, periodLabel, readFilters } from "../filters.js";
import * as fmt from "../format.js";

const content = document.getElementById("insights-content");
let current = null;
let filters = readFilters();

const card = (title, iconName, ...children) =>
  h("section", { class: "card insight-card" }, h("h2", { class: "insight-card__title" }, icon(iconName, "sm"), title), ...children);

function overviewTile(label, value, hint, extra = null) {
  return h("div", { class: "stat-tile" }, h("span", { class: "stat-tile__label" }, label),
    h("strong", { class: "stat-tile__value" }, value), extra, hint && h("span", { class: "stat-tile__hint" }, hint));
}

// ---------- Charts ----------
function trendChart(trend) {
  if (!trend.enough_data) {
    return h("p", { class: "chart-empty" }, icon("clock", "sm"),
      `Not enough tests over time yet. Each ${trend.bucket_days === 7 ? "week" : "month"} needs ${trend.min_samples_per_bucket}+ tests, and at least 3 periods need a score.`);
  }
  const fmtDate = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
  const bars = trend.buckets.map((b) => {
    const fill = h("span", { class: `trend__fill trend__fill--${b.band || "none"}` });
    fill.style.height = `${b.score ?? 6}%`;
    return h("div", { class: "trend__col" },
      h("span", { class: "trend__value" }, b.score ?? "–"),
      h("div", { class: "trend__track" }, fill),
      h("span", { class: "trend__label" }, fmtDate.format(new Date(b.start))));
  });
  const table = h("table", { class: "visually-hidden" },
    h("caption", {}, "Median connection score by period"),
    h("tr", {}, h("th", {}, "Period starting"), h("th", {}, "Score"), h("th", {}, "Tests")),
    trend.buckets.map((b) => h("tr", {}, h("td", {}, fmtDate.format(new Date(b.start))), h("td", {}, b.score ?? "not enough tests"), h("td", {}, String(b.sample_count)))));
  return h("div", { class: "trend" },
    h("div", { class: "trend__plot", "aria-hidden": "true" },
      h("span", { class: "trend__line trend__line--good" }, h("span", {}, "Good 70")),
      h("span", { class: "trend__line trend__line--fair" }, h("span", {}, "Fair 40")),
      h("div", { class: "trend__bars" }, bars)),
    table);
}

function densityChart(density) {
  if (!density.neighbourhoods) return h("p", { class: "chart-empty" }, "No neighbourhoods tested yet.");
  const max = Math.max(...density.buckets.map((b) => b.count), 1);
  return h("div", {},
    h("ul", { class: "hbar-list" }, density.buckets.map((b, i) => {
      const fill = h("span", { class: `hbar__fill hbar__fill--d${i + 1}` });
      fill.style.width = `${Math.max((b.count / max) * 100, b.count ? 3 : 0)}%`;
      return h("li", { class: "hbar" }, h("span", { class: "hbar__label" }, b.label),
        h("span", { class: "hbar__track", "aria-hidden": "true" }, fill), h("strong", { class: "hbar__value" }, String(b.count)));
    })),
    h("p", { class: "muted small" }, `${fmt.plural(density.neighbourhoods, "neighbourhood")} tested · typically ${density.median_tests_per_neighbourhood} tests each.`));
}

function providerList(providers, areaCode) {
  if (!providers.ranked.length) {
    return h("p", { class: "chart-empty" }, `Not enough tests per provider to compare them here yet (${providers.min_samples}+ each).`);
  }
  return h("div", {},
    h("ol", { class: "rank-list" }, providers.ranked.slice(0, 5).map((p, i) => h("li", { class: "rank-row" },
      h("span", { class: "rank-row__rank" }, String(i + 1)),
      h("span", { class: "rank-row__name" }, p.name, h("span", { class: "muted small" }, fmt.plural(p.sample_count, "test"))),
      h("span", { class: "bar", "aria-hidden": "true" }, barFill(p.score, p.band)),
      h("span", { class: "rank-row__score" }, String(p.score)), scoreBadge(p.band)))),
    h("a", { class: "text-link", href: `/providers?area=${encodeURIComponent(areaCode)}${filters.period ? `&period=${filters.period}` : ""}` },
      "Full provider comparison", icon("arrow-right", "sm")));
}

function areaRow(a) {
  return h("li", {}, h("a", { class: "region-item", href: `/map?area=${a.cell_id}` },
    h("span", { class: "region-item__text" },
      h("span", { class: "region-item__name" }, a.name || "Neighbourhood"),
      h("span", { class: "region-item__meta" }, `${fmt.plural(a.sample_count, "test")} · latest ${fmt.timeAgo(a.last_updated)}`)),
    h("span", { class: "region-item__score" }, String(a.score)), scoreBadge(a.band), icon("chevron-right", "sm")));
}

// ---------- Page ----------
function render(data) {
  const { area, summary } = data;
  const dist = data.neighbourhood_distribution;
  const scoredCount = dist.good + dist.fair + dist.weak;
  const isCountry = area.level === "country";
  const blocks = [
    h("div", { class: "context" },
      h("div", {},
        h("p", { class: "eyebrow" }, isCountry ? "Whole country" : area.label),
        h("h2", { class: "context__title" }, isCountry ? "All of India" : area.name)),
      h("p", { class: "context__meta" }, icon("clock", "sm"), `Tests from the ${periodLabel(filters.period)}`,
        filters.provider ? " · one provider only" : "")),
  ];

  if (!summary.sample_count) {
    blocks.push(h("div", { class: "card" }, emptyIllustration("No measurements here yet",
      `Connectivity insights will appear as genuine community measurements arrive (${isCountry ? "India" : area.name}, ${periodLabel(filters.period)}).`, testCta())));
    replace(content, ...blocks);
    return;
  }

  blocks.push(h("div", { class: "stat-grid stat-grid--4" },
    overviewTile("Connection score", summary.status === "ok" ? `${summary.score}/100` : "–",
      summary.status === "ok" ? fmt.BAND_VERDICT[summary.band].split(".")[0] : "Needs more tests across the area",
      scoreBadge(summary.band, summary.status)),
    overviewTile("Tests counted", fmt.number(summary.sample_count), "Genuine community measurements"),
    overviewTile("Neighbourhoods", fmt.number(summary.neighbourhood_count), `${scoredCount} with enough tests for a score`),
    overviewTile("Latest test", fmt.timeAgo(summary.last_updated) || "–", `Counting the ${periodLabel(filters.period)}`)));

  blocks.push(card("How neighbourhoods compare", "layers",
    h("p", { class: "muted small" }, "Neighbourhoods are areas about 1 km across. Each needs 5 or more tests for a score."),
    distributionBar(dist)));

  blocks.push(h("div", { class: "insights__pair" },
    card("Connection quality over time", "insights", trendChart(data.trend)),
    card("Measurement density", "users", h("p", { class: "muted small" }, "How many tests each neighbourhood has."), densityChart(data.density))));

  const weak = h("section", { class: "card insight-card", id: "weak-areas" },
    h("h2", { class: "insight-card__title" }, icon("alert", "sm"), "Weak connectivity areas"),
    data.weakest.length
      ? h("ul", { class: "region-list" }, data.weakest.map(areaRow))
      : h("p", { class: "chart-empty" }, scoredCount ? "No neighbourhoods here score Fair or Weak. That's good news." : "Not enough neighbourhoods with scores yet."));
  blocks.push(h("div", { class: "insights__pair" }, card("Provider comparison", "compare", providerList(data.providers, area.code)), weak));

  const childTitle = { country: "Compare states", state: "Compare districts", district: "Compare cities and towns" }[area.level];
  const withData = (data.children || []).filter((c) => c.summary.sample_count);
  if (childTitle && withData.length) {
    blocks.push(card(childTitle, "map",
      h("ul", { class: "region-list region-list--columns" }, withData.sort((a, b) => (b.summary.score ?? -1) - (a.summary.score ?? -1)).map((c) =>
        h("li", {}, h("button", { type: "button", class: "region-item", onClick: () => load(c.code) },
          h("span", { class: "region-item__text" }, h("span", { class: "region-item__name" }, c.name),
            h("span", { class: "region-item__meta" }, fmt.plural(c.summary.sample_count, "test"))),
          c.summary.status === "ok" ? h("span", { class: "region-item__score" }, String(c.summary.score)) : null,
          scoreBadge(c.summary.band, c.summary.status), icon("chevron-right", "sm")))))));
  }

  if (area.code.toUpperCase().startsWith("IN")) {
    const childLabel = { country: "states", state: "districts", district: "cities and towns" }[area.level];
    blocks.push(h("section", { class: "card export-card" },
      h("div", {}, h("h2", { class: "insight-card__title" }, icon("download", "sm"), "Download a report"),
        h("p", { class: "muted small" }, "Spreadsheet-ready CSV with area totals only, using the same area and filters. It never contains individual tests.")),
      h("div", { class: "download-row" },
        childLabel && h("a", { class: "button button--secondary", href: exportUrl(area.code, "children", filters), download: "" }, icon("download", "sm"), `By ${childLabel}`),
        h("a", { class: "button button--secondary", href: exportUrl(area.code, "neighbourhoods", filters), download: "" }, icon("download", "sm"), "By neighbourhood"))));
  }
  replace(content, ...blocks);
  if (window.location.hash === "#weak-areas") document.getElementById("weak-areas")?.scrollIntoView();
}

async function load(area, { push = true } = {}) {
  current = area;
  if (push) setAreaParam(area);
  replace(content, loading(6));
  try {
    const data = await api.insights(area, filters);
    if (current !== area) return;
    bar.setLabel(data.area.level === "country" ? "" : data.area.name);
    render(data);
  } catch (error) {
    replace(content, errorMessage(error, () => load(area, { push: false })));
  }
}

const bar = createAreaBar(document.getElementById("area-bar"), {
  onChange: (code) => load(code),
  onError: (error) => replace(content, errorMessage(error, () => load(current, { push: false }))),
});
createFilters(document.getElementById("filters"), {
  onChange: (next) => { filters = next; load(current, { push: false }); },
});
window.addEventListener("popstate", () => load(getAreaParam() || "IN", { push: false }));
load(getAreaParam() || "IN", { push: false });
