// Compare Providers: rank providers in a chosen area by their median Connection Score.
import { api } from "../api.js";
import { createAreaBar } from "../area-bar.js";
import { barFill, errorMessage, loading, sampleLine, scoreBadge, stateMessage, testCta } from "../components.js";
import { getAreaParam, h, icon, replace, setAreaParam } from "../dom.js";
import { createFilters, periodLabel } from "../filters.js";
import * as fmt from "../format.js";

const content = document.getElementById("providers-content");
let current = null;
let filters = { period: new URLSearchParams(location.search).get("period") || "" };

function providerCard(p, rank) {
  return h("li", { class: "card provider-card" },
    h("div", { class: "provider-card__head" },
      h("span", { class: "provider-card__rank", "aria-label": `Rank ${rank}` }, String(rank)),
      h("div", { class: "provider-card__title" },
        h("h3", {}, p.name),
        h("span", { class: "muted small" }, fmt.PROVIDER_KIND[p.kind] || "")),
      h("div", { class: "provider-card__score" }, h("strong", {}, String(p.score)), h("span", { class: "muted" }, "/100"))),
    h("span", { class: "bar bar--lg", role: "img", "aria-label": `Connection score ${p.score} out of 100` }, barFill(p.score, p.band)),
    h("div", { class: "provider-card__facts" },
      scoreBadge(p.band),
      h("span", {}, icon("download", "sm"), `${fmt.speed(p.download_mbps)} Mbps typical download`),
      h("span", {}, icon("pulse", "sm"), `${p.latency_ms} ms response time`),
      h("span", { class: "muted" }, fmt.plural(p.sample_count, "test"))));
}

function render(data) {
  const { area, summary, providers } = data;
  const title = area.level === "country" ? "All of India" : area.name;
  const blocks = [
    h("div", { class: "area-heading" },
      h("p", { class: "eyebrow" }, area.level === "country" ? "Whole country" : area.label),
      h("h2", {}, title),
      h("p", { class: "muted small" }, `Tests from the ${periodLabel(filters.period)}.`),
      summary.sample_count ? sampleLine(summary) : null),
  ];

  if (providers.ranked.length) {
    const [best, next] = providers.ranked;
    blocks.push(h("div", { class: "verdict" },
      h("span", { class: "verdict__icon" }, icon("trophy")),
      h("p", {}, next
        ? [h("strong", {}, best.name), ` performs best here: ${best.score}/100 from ${fmt.plural(best.sample_count, "test")}. `,
           `${next.name} is next at ${next.score}/100${best.score - next.score <= 3 ? ", so the difference is small" : ""}.`]
        : [h("strong", {}, best.name), ` is the only provider with enough tests to rank here (${best.score}/100 from ${fmt.plural(best.sample_count, "test")}).`])));
    blocks.push(h("ol", { class: "provider-cards" }, providers.ranked.map((p, i) => providerCard(p, i + 1))));
  } else {
    blocks.push(stateMessage({
      iconName: "compare", title: "Not enough measurements to compare providers in this area yet.",
      text: `Each provider needs at least ${providers.min_samples} tests in ${area.level === "country" ? "India" : "this area"} (${periodLabel(filters.period)}) before we rank it.`,
      action: testCta("Add your test"),
    }));
  }

  if (providers.insufficient.length) {
    blocks.push(h("section", { class: "section-sm" },
      h("h3", { class: "h3" }, "Not enough tests yet"),
      h("ul", { class: "chip-list" }, providers.insufficient.map((p) =>
        h("li", { class: "chip chip--static" }, p.name, h("span", { class: "muted" }, ` · ${p.sample_count} of ${providers.min_samples}`))))));
  }
  if (providers.unidentified_count) {
    blocks.push(h("p", { class: "coverage-note" }, icon("info", "sm"),
      `${fmt.plural(providers.unidentified_count, "test")} here came from providers we couldn't identify or don't list separately, so ${providers.unidentified_count === 1 ? "it isn't" : "they aren't"} ranked.`));
  }
  blocks.push(h("p", { class: "muted small" }, "Ranked by median Connection Score. Providers need enough tests in this area to be ranked fairly."));
  replace(content, ...blocks);
}

async function load(area, { push = true } = {}) {
  current = area;
  if (push) setAreaParam(area);
  replace(content, loading(4));
  try {
    const data = await api.rankings(area, filters);
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
  provider: false,
  onChange: (next) => { filters = next; load(current, { push: false }); },
});
window.addEventListener("popstate", () => load(getAreaParam() || "IN", { push: false }));
load(getAreaParam() || "IN", { push: false });
