# Design System

The feel we're after is minimal, premium and welcoming: Apple-like calm with Google Maps familiarity. Everything lives in three stylesheets:

| File | Contains |
|---|---|
| `frontend/static/css/tokens.css` | **Design tokens**: named variables for every colour, size, radius, shadow and animation speed |
| `frontend/static/css/base.css` | Reset, typography, page layout, header, top and bottom navigation, footer |
| `frontend/static/css/components.css` | Reusable pieces: buttons, cards, badges, notices, empty states |
| `frontend/static/css/pages.css` | Page layouts (home, insights, providers, speed test, about, how it works), built only from tokens |
| `frontend/static/css/map.css` | The Explore India map |

> **In plain words: design tokens.** Instead of writing `#263B32` in 40 places, we write it once as `--color-forest` and use the name everywhere. Changing the brand colour then means editing one line.

**Rule:** components use semantic tokens (`--color-text`, `--color-primary`), never raw hex values.

## Colour

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#F7F8F5` warm off-white | Page background |
| `--color-surface` | `#FFFFFF` | Cards |
| `--color-surface-muted` | `#E9EDE8` neutral grey | Hover states, notices |
| `--color-accent-soft` | `#DCE9DF` soft sage | Active nav, icon tiles, soft cards |
| `--color-accent` | `#638B72` natural green | Icons, borders, focus ring, large text **only** |
| `--color-text` / `--color-primary` | `#263B32` deep forest | Body text, primary buttons |
| `--color-text-muted` | `#55675D` | Secondary text |

### Contrast (WCAG 2.2 AA needs 4.5:1 for normal text)
| Pair | Ratio | OK for |
|---|---|---|
| Forest on off-white | ~11:1 | Everything |
| White on forest (buttons) | ~11:1 | Everything |
| Muted `#55675D` on off-white | ~5.6:1 | Body text |
| Natural green on off-white | ~3.6:1 | Large text, icons, focus outlines (≥3:1). **Not body text** |

### Score bands
| Band | Fill (map) | Badge background / text |
|---|---|---|
| Good (70–100) | `#638B72` | `#DCE9DF` / `#263B32` |
| Fair (40–69) | `#C99A3E` | `#F4E9CF` / `#6B4E0E` |
| Weak (0–39) | `#B65F4B` | `#F3DCD5` / `#7E3626` |
| Not enough tests | `#C9D1C8` | `#E9EDE8` / `#55675D` |

Colour is **never the only signal**: every score shows a word ("Good") and, on the map, a pattern or icon too, so colour-blind users aren't left out. Final map colours will be re-checked for colour-blind distinguishability in Phase 8.

## Typography
- **Inter** (variable, SIL Open Font License), **self-hosted** in `static/fonts/`, so no font CDN sees our visitors. It falls back to system fonts.
- Base size **17 px** for comfortable reading at all ages. Headings scale smoothly between phone and desktop with `clamp()`.

## Map tokens
| Token | Use |
|---|---|
| `--map-sea` | Background outside India |
| `--map-land` | Areas with no tests |
| `--map-insufficient` (+ `-stroke`, dashed) | Some tests, not enough for a score |
| `--map-boundary` | Subtle state and district lines |
Band colours fill an area **only** when the server marks it `ok`.

## Shape, depth and motion
- Radii: 8 / 14 / 20 / 28 px, with fully rounded "pill" buttons.
- Shadows: three soft levels tinted with forest green, never harsh black.
- Motion: 150–250 ms ease-out on hover and press only. `prefers-reduced-motion` sets every duration to 0.

## Layout and navigation
- **Desktop/tablet (≥ 768 px):** a fixed left sidebar holding the brand, the 5 main pages, "Learn more" (About, How it works, Privacy), and a footer (coverage, privacy promise, version).
  - It's full width (15.5 rem) from 1200 px and an icon rail (4.75 rem) below that, with tooltips on hover and keyboard focus.
  - The toggle button remembers the choice (`localStorage`, `js/shell.js`). Content sits beside the sidebar, and only user-initiated changes animate.
- **Phones (< 768 px):** a compact top bar (brand + "More pages" menu sheet) and a bottom tab bar with the 5 main pages.
- The current page is marked with `aria-current="page"` plus a sage highlight and accent bar.
- Touch targets are at least 44 × 44 px. Content max width is 76 rem.
- Radii follow a controlled scale: 8 / 12 / 16 / 24 px.

## Illustrations (original, no licensing restrictions)
| File | Use |
|---|---|
| `assets/india-states.svg` | Generated from the LGD state boundaries by `scripts/build_illustrations.py`. Used in the home hero (with the Chennai pilot pin) and empty states |
| `assets/city-connectivity.svg` | Home privacy section, About page |
| `assets/how-measurements-work.svg` | "Test → ~150 m area → map" on Home and How it works |

## Components

| Class | Purpose |
|---|---|
| `.button--primary` / `.button--secondary` | Main and secondary actions (52 px tall, pill shape) |
| `.card`, `.card--soft`, `.card__icon` | Content containers |
| `.card-grid--2/3` | Responsive grids (stacked on phones) |
| `.page-header`, `.eyebrow`, `.lead` | Page title area |
| `.score-badge--good/fair/weak/none` | Score labels with a colour dot |
| `.notice` | Gentle informational message |
| `.checklist` | Icon-led lists |
| `.empty-state` + `coming_soon()` macro | Honest placeholder that never shows fake data |
| `icon(name, size)` macro / `icon()` in `dom.js` | Line icons from one inline SVG sprite (`partials/sprite.html`) |
| `areaSummary()` (`components.js`) | Score ring, verdict, sample count, freshness, medians, or the honest insufficient-data checklist |
| `.metric-grid`, `.score-ring`, `.requirements` | Parts of the summary |
| `.region-item` / `.region-list` | Tappable lists of states, districts and neighbourhoods (also the keyboard alternative to clicking the map) |
| `createAreaPicker()` | Accessible search combobox |
| `.provider-card`, `.provider-rows`, `.bar` | Provider comparison |
| `.stat-tile`, `.stacked-bar`, `.legend-list` | Insights |
| `.sheet` (`<dialog>`) | Location-permission explainer (bottom sheet on phones) |
| `.segmented`, `.toggle` | Speed-test choices |
| `.gauge` (`gauge.js`) | SVG speedometer with a non-linear scale |
| `.sidebar`, `.topbar`, `.bottom-nav`, `#menu-sheet` | App shell |
| `.toolbar` | Search + filters row (Insights, Compare Providers) |
| `.stat-grid--4` | Four equal overview cards (two-up on phones) |
| `distributionBar()`, `emptyIllustration()` | Shared chart and empty state (`components.js`) |
| `.trend`, `.hbar-list`, `.rank-list` | Minimal charts with labels, hidden data tables for screen readers |
| `.verdict` | Plain-language provider summary |

## Security constraint on markup
The Content-Security-Policy blocks inline `<script>` and `style="..."` attributes. JS sets dynamic widths through the CSSOM (`el.style.width`), which CSP allows. All styling goes in the CSS files and all behaviour in `.js` files. A test enforces this.
