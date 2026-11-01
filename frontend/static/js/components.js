// Reusable UI pieces shared by the map, compare and insights screens.
import { h, icon } from "./dom.js";
import * as fmt from "./format.js";

const BIG_AREAS = new Set(["country", "state", "district"]);

export function scoreBadge(band, status = "ok") {
  if (band) return h("span", { class: `score-badge score-badge--${band}` }, fmt.BAND_LABEL[band]);
  return h("span", { class: "score-badge score-badge--none" }, status === "no_data" ? "No tests yet" : "Not enough tests");
}

export function metricGrid(medians) {
  return h("dl", { class: "metric-grid" },
    fmt.METRICS.map((m) => h("div", { class: "metric" },
      h("dt", { class: "metric__label" }, icon(m.icon, "sm"), m.label),
      h("dd", { class: "metric__value" }, fmt.metricValue(m.key, medians?.[m.key]), h("span", { class: "metric__unit" }, ` ${m.unit}`)),
      h("dd", { class: "metric__hint" }, m.hint),
    )));
}

export function sampleLine(summary) {
  const parts = [`Based on ${fmt.plural(summary.sample_count, "test")}`];
  if (summary.neighbourhood_count > 1) parts[0] += ` in ${fmt.plural(summary.neighbourhood_count, "neighbourhood")}`;
  const ago = fmt.timeAgo(summary.last_updated);
  return h("p", { class: "summary__meta" },
    h("span", {}, icon("users", "sm"), parts[0]),
    ago && h("span", {}, icon("clock", "sm"), `Latest test ${ago}`));
}

export function requirementList(summary) {
  const r = summary.requirement;
  const items = [[summary.sample_count >= r.min_samples, `${fmt.number(summary.sample_count)} of ${r.min_samples} tests`]];
  if (r.min_neighbourhoods > 1) {
    items.push([summary.neighbourhood_count >= r.min_neighbourhoods,
      `${fmt.number(summary.neighbourhood_count)} of ${r.min_neighbourhoods} neighbourhoods`]);
  }
  if (r.min_districts > 1) {
    items.push([summary.district_count >= r.min_districts, `${summary.district_count} of ${r.min_districts} districts`]);
  }
  return h("ul", { class: "requirements", "aria-label": "What's needed for a score" },
    items.map(([met, text]) => h("li", { class: met ? "is-met" : "" }, icon(met ? "check" : "circle", "sm"),
      h("span", {}, text, h("span", { class: "visually-hidden" }, met ? " (done)" : " (still needed)")))));
}

export function testCta(text = "Test my connection") {
  return h("a", { class: "button button--primary", href: "/speed-test" }, icon("gauge"), text);
}

/** Score, verdict, sample count, freshness and medians — or an honest insufficient-data state. */
export function areaSummary({ summary, area }) {
  const level = area.level;
  if (summary.status === "ok") {
    return h("div", { class: "summary" },
      h("div", { class: "summary__headline" },
        h("div", { class: `score-ring score-ring--${summary.band}`, role: "img",
          "aria-label": `Connection score ${summary.score} out of 100, ${fmt.BAND_LABEL[summary.band]}` },
          h("span", { class: "score-ring__value", "aria-hidden": "true" }, String(summary.score)),
          h("span", { class: "score-ring__max", "aria-hidden": "true" }, "/100")),
        h("div", {},
          scoreBadge(summary.band),
          h("p", { class: "summary__verdict" }, fmt.BAND_VERDICT[summary.band]))),
      sampleLine(summary),
      metricGrid(summary.medians),
      BIG_AREAS.has(level) && h("p", { class: "coverage-note" }, icon("info", "sm"),
        `Reflects the places where people have tested, not every street in ${area.name}.`));
  }

  if (summary.status === "insufficient") {
    return h("div", { class: "summary summary--empty" },
      scoreBadge(null, "insufficient"),
      h("p", { class: "summary__verdict" }, "We need a few more tests here before we can show a fair score."),
      requirementList(summary),
      sampleLine(summary),
      testCta("Add a test here"));
  }

  return h("div", { class: "summary summary--empty" },
    scoreBadge(null, "no_data"),
    h("p", { class: "summary__verdict" }, "No measurements yet in this area."),
    h("p", { class: "muted" }, "Be one of the first. Every shared test helps your neighbours."),
    testCta());
}

export function providerRows(ranking, { limit = Infinity } = {}) {
  const rows = ranking.ranked.slice(0, limit);
  if (!rows.length) return null;
  return h("ol", { class: "provider-rows" }, rows.map((p, i) => h("li", { class: "provider-row" },
    h("span", { class: "provider-row__rank", "aria-hidden": "true" }, String(i + 1)),
    h("span", { class: "provider-row__name" }, p.name),
    h("span", { class: "bar", "aria-hidden": "true" }, barFill(p.score, p.band)),
    h("span", { class: "provider-row__score" }, String(p.score)),
  )));
}

export function barFill(score, band) {
  const fill = h("span", { class: `bar__fill bar__fill--${band}` });
  fill.style.width = `${Math.max(4, score)}%`;
  return fill;
}

export function stateMessage({ iconName = "info", title, text, action = null, tone = "" }) {
  return h("div", { class: `state-message ${tone ? `state-message--${tone}` : ""}` },
    h("div", { class: `card__icon ${tone === "error" ? "card__icon--warn" : ""}` }, icon(iconName)),
    h("h2", { class: "h3" }, title),
    text && h("p", { class: "muted" }, text),
    action);
}

export function errorMessage(error, retry) {
  return stateMessage({
    iconName: "alert", tone: "error", title: "Something went wrong",
    text: error?.message || "Please try again.",
    action: retry && h("button", { type: "button", class: "button button--secondary", onClick: retry }, icon("refresh"), "Try again"),
  });
}

export function loading(lines = 3) {
  return h("div", { class: "loading", "aria-busy": "true", "aria-label": "Loading" },
    Array.from({ length: lines }, (_, i) => h("div", { class: `skeleton skeleton--line ${i === 0 ? "skeleton--title" : ""}` })));
}

/** Good / Fair / Weak / Not enough tests across neighbourhoods, as a bar plus labelled counts. */
export function distributionBar(dist) {
  const parts = [["good", "Good"], ["fair", "Fair"], ["weak", "Weak"], ["insufficient", "Not enough tests"]];
  const total = parts.reduce((sum, [key]) => sum + dist[key], 0);
  const bar = h("div", { class: "stacked-bar", role: "img",
    "aria-label": parts.map(([k, l]) => `${l}: ${dist[k]}`).join(", ") });
  for (const [key] of parts) {
    if (!dist[key]) continue;
    const seg = h("span", { class: `stacked-bar__seg stacked-bar__seg--${key}` });
    seg.style.flexGrow = String(dist[key]);
    bar.append(seg);
  }
  return h("div", { class: "distribution" },
    total ? bar : null,
    h("ul", { class: "legend-list" }, parts.map(([key, label]) => h("li", {},
      h("span", { class: `legend-swatch legend-swatch--${key}` }), `${label} `, h("strong", {}, String(dist[key]))))));
}

/** A small empty state with the India illustration. */
export function emptyIllustration(title, text, action = null) {
  return h("div", { class: "empty-illustration" },
    h("img", { src: "/static/assets/india-states.svg", alt: "", width: "120", height: "134", loading: "lazy" }),
    h("div", {}, h("h3", { class: "h3" }, title), text && h("p", { class: "muted" }, text), action));
}
