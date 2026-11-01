// Speed Test screen: choose → (optional) share consent + location → test → results → save.
import { api } from "../api.js";
import { errorMessage, metricGrid } from "../components.js";
import { h, icon, replace } from "../dom.js";
import * as fmt from "../format.js";
import { createGauge } from "../gauge.js";
import { encode } from "../geohash.js";
import { requestLocation } from "../location.js";
import { ENGINE_ID, TestCancelled, cancelSpeedTest, runSpeedTest } from "../speedtest-engine.js";

const MAX_ACCURACY_M = 250; // can't honestly place a result in a 150 m block beyond this
const DAILY_TEST_LIMIT = 40; // M-Lab Acceptable Use Policy: interactive users, per day
const HISTORY_KEY = "speedspot:test-times";

const root = document.getElementById("speedtest");
const gauge = createGauge(document.getElementById("gauge"));
const live = document.getElementById("live-status");
const startButton = document.getElementById("start-test");
const shareToggle = document.getElementById("share-toggle");
const resultsEl = document.getElementById("results");
const errorEl = document.getElementById("test-error");
const providerChip = document.getElementById("provider-chip");

const ACTIVITIES = [
  { name: "Browsing and messaging", ok: (r) => r.download_mbps >= 2 && r.latency_ms < 300, great: (r) => r.download_mbps >= 10 && r.latency_ms < 100 },
  { name: "HD video streaming", ok: (r) => r.download_mbps >= 5, great: (r) => r.download_mbps >= 25 },
  { name: "Video calls", ok: (r) => r.upload_mbps >= 1.5 && r.latency_ms < 200 && r.jitter_ms < 40, great: (r) => r.upload_mbps >= 5 && r.latency_ms < 80 && r.jitter_ms < 20 },
  { name: "Online gaming", ok: (r) => r.latency_ms < 100 && r.jitter_ms < 30, great: (r) => r.latency_ms < 40 && r.jitter_ms < 10 },
  { name: "Uploading large files", ok: (r) => r.upload_mbps >= 5, great: (r) => r.upload_mbps >= 25 },
];

// ---------- Daily limit (stored only in this browser) ----------
function recentTests() {
  try {
    const cutoff = Date.now() - 24 * 3600 * 1000;
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]").filter((t) => t > cutoff);
  } catch {
    return [];
  }
}

function rememberTest() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify([...recentTests(), Date.now()]));
  } catch { /* private mode: the limit simply isn't tracked */ }
}

// ---------- Provider ----------
async function showProvider() {
  const text = providerChip.querySelector("span");
  try {
    const me = await api.myProvider();
    providerChip.dataset.status = me.status;
    text.textContent = me.status === "identified" ? `Your provider: ${me.provider.name}`
      : me.status === "other_isp" ? `Your provider: ${me.network}`
      : me.status === "vpn_or_hosting" ? "VPN or cloud network detected" : "Provider not recognised";
    providerChip.title = me.message;
    if (me.status === "vpn_or_hosting") {
      providerChip.after(h("div", { class: "notice notice--warn" }, icon("alert"), h("p", {}, me.message)));
    }
  } catch {
    text.textContent = "Provider not recognised";
  }
}

function showStep(name) {
  root.querySelectorAll("[data-step]").forEach((el) => { el.hidden = el.dataset.step !== name; });
}

function setPhase(phase) {
  const order = ["server", "download", "upload"];
  root.querySelectorAll("#phase-list li").forEach((li) => {
    const idx = order.indexOf(li.dataset.phase);
    li.classList.toggle("is-active", li.dataset.phase === phase);
    li.classList.toggle("is-done", idx < order.indexOf(phase));
  });
}

async function placeForSharing() {
  try {
    const pos = await requestLocation("We'll place your result in its ~150 m area on the community map.");
    if (pos.accuracy > MAX_ACCURACY_M) {
      return { cell: null, note: `Your location is only accurate to about ${Math.round(pos.accuracy)} m, so we won't place this result on the map. The test still works.` };
    }
    // The exact position is turned into a ~150 m area code here and then forgotten.
    return { cell: encode(pos.lat, pos.lng, 7), note: null };
  } catch (error) {
    const note = error.code === "cancelled"
      ? "No problem. This result won't be added to the map."
      : `${error.message} This result won't be added to the map.`;
    return { cell: null, note };
  }
}

function activityList(result) {
  return h("ul", { class: "activity-list" }, ACTIVITIES.map((a) => {
    const level = a.great(result) ? "great" : a.ok(result) ? "ok" : "poor";
    const label = { great: "Great", ok: "Works", poor: "May struggle" }[level];
    return h("li", { class: `activity activity--${level}` },
      icon(level === "poor" ? "alert" : "check", "sm"), h("span", { class: "activity__name" }, a.name),
      h("span", { class: "activity__level" }, label));
  }));
}

async function shareResult(result, connectionType, cell, statusEl) {
  replace(statusEl, h("p", { class: "muted" }, "Adding your result to the community map…"));
  try {
    const saved = await api.submitMeasurement({
      submission_id: result.submissionId, cell_id: cell, download_mbps: round(result.download_mbps, 2), upload_mbps: round(result.upload_mbps, 2),
      latency_ms: round(result.latency_ms, 1), jitter_ms: round(result.jitter_ms, 1),
      connection_type: connectionType, engine: ENGINE_ID,
    });
    replace(statusEl, h("div", { class: `notice ${saved.counted ? "notice--success" : "notice--warn"}` },
      icon(saved.counted ? "check" : "info"),
      h("p", {}, saved.counted ? "Thank you! Your result was added to the community map." : `Thanks, your result was saved. ${saved.message}`),
    ), h("a", { class: "button button--secondary button--block", href: `/map?area=${saved.neighbourhood}` }, icon("map"), "See your area on the map"));
  } catch (error) {
    if (error.code === "duplicate_submission") {
      replace(statusEl, h("div", { class: "notice notice--success" }, icon("check"), h("p", {}, "This result was already added to the map.")));
      return;
    }
    replace(statusEl, h("div", { class: "notice notice--warn" }, icon("alert"), h("p", {}, `Your result couldn't be added to the map: ${error.message}`),
      h("button", { type: "button", class: "text-button", onClick: () => shareResult(result, connectionType, cell, statusEl) }, icon("refresh", "sm"), "Try again")));
  }
}

const round = (v, d) => Math.round(v * 10 ** d) / 10 ** d;

function renderResults(result, { connectionType, cell, shareNote }) {
  const score = fmt.connectionScore(result);
  const band = fmt.bandFor(score);
  const shareStatus = h("div", { class: "share-status" });

  replace(resultsEl,
    h("div", { class: "result-hero" },
      h("div", { class: `score-ring score-ring--lg score-ring--${band}`, role: "img", "aria-label": `Connection score ${score} out of 100, ${fmt.BAND_LABEL[band]}` },
        h("span", { class: "score-ring__value", "aria-hidden": "true" }, String(score)),
        h("span", { class: "score-ring__max", "aria-hidden": "true" }, "/100")),
      h("span", { class: `score-badge score-badge--${band}` }, fmt.BAND_LABEL[band]),
      h("p", { class: "result-hero__verdict" }, fmt.BAND_VERDICT[band]),
      result.server && h("p", { class: "muted small" }, `Tested against a server in ${result.server}`)),
    metricGrid(result),
    h("h2", { class: "h3 section-title" }, "What this connection is good for"),
    activityList(result),
    shareNote && h("div", { class: "notice notice--quiet" }, icon("info"), h("p", {}, shareNote)),
    shareStatus,
    h("details", { class: "details" },
      h("summary", {}, "Technical details"),
      h("dl", { class: "details__list" },
        h("dt", {}, "Test engine"), h("dd", {}, "M-Lab ndt7 (Measurement Lab), about 10 seconds each way"),
        h("dt", {}, "Server"), h("dd", {}, result.server || "Chosen automatically by M-Lab"),
        h("dt", {}, "Download / upload"), h("dd", {}, `${result.download_mbps.toFixed(2)} / ${result.upload_mbps.toFixed(2)} Mbps (average over the test)`),
        h("dt", {}, "Response time"), h("dd", {}, `${result.latency_ms.toFixed(1)} ms: the fastest round trip seen during the test (TCP MinRTT)`),
        h("dt", {}, "Stability"), h("dd", {}, `${result.jitter_ms.toFixed(1)} ms: how much round trips varied while the line was busy (TCP RTTVar). Lower is steadier.`),
        h("dt", {}, "Connection Score"), h("dd", {}, "100 × (0.40 download + 0.20 upload + 0.25 response + 0.15 stability), each capped at a good level. Calculated again on our server if you share."))),
    h("button", { type: "button", class: "button button--primary button--block", onClick: reset }, icon("refresh"), "Test again"),
  );
  if (cell) shareResult(result, connectionType, cell, shareStatus);
}

function reset() {
  gauge.reset();
  live.textContent = "Ready when you are.";
  startButton.disabled = false;
  showStep("intro");
  startButton.focus();
}

async function start() {
  if (!navigator.onLine) {
    replace(errorEl, errorMessage({ message: "You seem to be offline. Connect to the internet and try again." }, reset));
    showStep("error");
    return;
  }
  if (recentTests().length >= DAILY_TEST_LIMIT) {
    replace(errorEl, errorMessage({ message: `You've run ${DAILY_TEST_LIMIT} tests in the last 24 hours, which is M-Lab's daily limit. Please try again tomorrow.` }, reset));
    showStep("error");
    return;
  }
  startButton.disabled = true;
  const connectionType = root.querySelector('input[name="connection"]:checked')?.value || "unknown";
  const { cell, note } = shareToggle.checked ? await placeForSharing() : { cell: null, note: null };

  showStep("running");
  setPhase("server");
  gauge.reset("Connecting");
  live.textContent = "Finding the nearest test server…";

  try {
    const result = await runSpeedTest({
      onPhase: (phase, info) => {
        setPhase(phase);
        if (phase === "download") live.textContent = info?.server ? `Testing download (server in ${info.server})…` : "Testing download…";
        if (phase === "upload") { live.textContent = "Testing upload…"; gauge.set(0, "Upload"); }
      },
      onProgress: (phase, mbps) => gauge.set(mbps, phase === "download" ? "Download" : "Upload"),
    });
    rememberTest();
    // A fresh random ID per test lets a retried upload be recognised instead of counted twice.
    result.submissionId = crypto.randomUUID();
    gauge.set(result.download_mbps, "Download");
    live.textContent = "Test complete.";
    renderResults(result, { connectionType, cell, shareNote: note });
    showStep("results");
    resultsEl.querySelector(".score-ring")?.focus?.();
  } catch (error) {
    if (error instanceof TestCancelled) {
      gauge.reset("Cancelled");
      live.textContent = "Test cancelled. Nothing was measured or saved.";
      startButton.disabled = false;
      showStep("intro");
      startButton.focus();
      return;
    }
    live.textContent = "The test didn't finish.";
    replace(errorEl, errorMessage(error, reset));
    showStep("error");
  }
}

document.getElementById("cancel-test").addEventListener("click", cancelSpeedTest);

startButton.addEventListener("click", start);
showProvider();
