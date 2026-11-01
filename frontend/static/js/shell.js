// App shell: collapsible sidebar (≥768px) and the phone "More" menu sheet.
const sidebar = document.getElementById("sidebar");
const toggle = document.getElementById("sidebar-toggle");
const STORAGE_KEY = "speedspot:sidebar";
const wide = window.matchMedia("(min-width: 1200px)");

function storedPreference() {
  try {
    return localStorage.getItem(STORAGE_KEY); // "collapsed" | "expanded" | null
  } catch {
    return null;
  }
}

function apply(collapsed) {
  sidebar.dataset.collapsed = String(collapsed);
  document.body.dataset.sidebar = collapsed ? "collapsed" : "expanded";
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.querySelector("[data-label]").textContent = collapsed ? "Expand sidebar" : "Collapse sidebar";
  // Leaflet maps need to know their container changed size.
  window.dispatchEvent(new CustomEvent("speedspot:layout"));
}

function currentDefault() {
  const pref = storedPreference();
  if (pref) return pref === "collapsed";
  return !wide.matches; // icon-only on tablets and small laptops, full on wide screens
}

apply(currentDefault());
requestAnimationFrame(() => requestAnimationFrame(() => document.body.classList.add("shell-ready")));
wide.addEventListener("change", () => { if (!storedPreference()) apply(currentDefault()); });
toggle.addEventListener("click", () => {
  const collapsed = sidebar.dataset.collapsed !== "true";
  try {
    localStorage.setItem(STORAGE_KEY, collapsed ? "collapsed" : "expanded");
  } catch { /* private mode: the choice lasts for this page only */ }
  apply(collapsed);
});

// ---------- Phone menu ----------
const menu = document.getElementById("menu-sheet");
document.getElementById("menu-open").addEventListener("click", () => menu.showModal());
menu.addEventListener("click", (event) => {
  // Close on the close button or a tap on the backdrop (the dialog element itself).
  if (event.target === menu || event.target.closest("[data-close]")) menu.close();
});
