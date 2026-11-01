// SVG speedometer. Non-linear scale so both 3 Mbps and 300 Mbps are readable.
const SVG_NS = "http://www.w3.org/2000/svg";
const TICKS = [0, 5, 10, 25, 50, 100, 250, 500, 1000];
const LABELLED = new Set([0, 10, 50, 100, 500, 1000]);
const START = 150; // degrees, measured clockwise from 3 o'clock
const SWEEP = 240;
const CX = 120;
const CY = 120;
const R = 96;

function svg(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function point(angle, radius) {
  const rad = (angle * Math.PI) / 180;
  return [CX + radius * Math.cos(rad), CY + radius * Math.sin(rad)];
}

function arcPath(radius) {
  const [x1, y1] = point(START, radius);
  const [x2, y2] = point(START + SWEEP, radius);
  return `M ${x1} ${y1} A ${radius} ${radius} 0 1 1 ${x2} ${y2}`;
}

export function fraction(mbps) {
  const v = Math.max(0, Math.min(mbps, TICKS[TICKS.length - 1]));
  for (let i = 0; i < TICKS.length - 1; i++) {
    if (v <= TICKS[i + 1]) return (i + (v - TICKS[i]) / (TICKS[i + 1] - TICKS[i])) / (TICKS.length - 1);
  }
  return 1;
}

export function createGauge(container) {
  const root = svg("svg", { viewBox: "0 0 240 200", class: "gauge__svg" });
  root.append(svg("path", { d: arcPath(R), class: "gauge__track", pathLength: "100" }));
  const value = svg("path", { d: arcPath(R), class: "gauge__value", pathLength: "100" });
  root.append(value);

  TICKS.forEach((tick, i) => {
    if (!LABELLED.has(tick)) return;
    const [x, y] = point(START + (SWEEP * i) / (TICKS.length - 1), R - 22);
    const label = svg("text", { x, y, class: "gauge__tick", "text-anchor": "middle", "dominant-baseline": "middle" });
    label.textContent = tick >= 1000 ? "1G" : String(tick);
    root.append(label);
  });

  const number = svg("text", { x: CX, y: CY + 6, class: "gauge__number", "text-anchor": "middle" });
  const unit = svg("text", { x: CX, y: CY + 30, class: "gauge__unit", "text-anchor": "middle" });
  const phase = svg("text", { x: CX, y: CY + 62, class: "gauge__phase", "text-anchor": "middle" });
  root.append(number, unit, phase);
  container.replaceChildren(root);

  function set(mbps, label = "") {
    value.style.strokeDashoffset = String(100 - fraction(mbps) * 100);
    number.textContent = mbps >= 100 ? Math.round(mbps) : mbps.toFixed(1);
    unit.textContent = "Mbps";
    phase.textContent = label;
  }

  function reset(label = "Ready") {
    value.style.strokeDashoffset = "100";
    number.textContent = "0";
    unit.textContent = "Mbps";
    phase.textContent = label;
  }

  reset();
  return { set, reset };
}
