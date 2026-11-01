// Tiny DOM helpers. Text is always set with textContent, never innerHTML, so data
// from the API can't inject markup (XSS-safe by construction).

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * h("a", { class: "button", href: "/map", onClick: fn, dataset: { code } }, "Label", child)
 * Strings become text nodes; null/false children are skipped.
 */
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  append(el, children);
  return el;
}

export function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

export function icon(name, size = "") {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", size ? `icon icon--${size}` : "icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

export function replace(el, ...children) {
  el.replaceChildren();
  return append(el, children);
}

export const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function debounce(fn, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

export function getAreaParam() {
  return new URLSearchParams(window.location.search).get("area");
}

export function setAreaParam(code, { replace: replaceState = false } = {}) {
  const url = new URL(window.location.href);
  if (code && code !== "IN") url.searchParams.set("area", code);
  else url.searchParams.delete("area");
  if (url.href === window.location.href) return;
  history[replaceState ? "replaceState" : "pushState"]({ area: code }, "", url);
}
