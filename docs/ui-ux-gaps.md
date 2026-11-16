# SketchMyInfra — UI/UX gaps (living list)

Things that make the platform feel worse than it should. Add to this as you find more.
Status: `open` / `planned` / `fixed (PR link)`.

Audit date: 2026-11-16. Measured on the workspace UI (`frontend/index.html`, `css/workspace.css`) in mock mode
with a synthetic 900×2400 diagram.

## P0 — breaks the core loop (generate → look → download)

### 1. Big diagram makes the whole page big — `fixed (feat/app-shell-layout)`
- **Measured:** at 1440×900 the document grows to **2160px** tall; at 1024×768 to 974px; on a 375px phone to 1879px.
- **Why it happens:** `body` is `min-h-screen` (grows past the viewport, never caps). `#diagram-image` is
  `max-w-full h-auto`, so its height follows the image. The scroll container (`overflow-auto` on the canvas div)
  never becomes the scroller because nothing above it has a fixed height.
- **What the user feels:** header, Generate button and the PNG/SVG toolbar scroll out of view. The code panel stretches
  to 2000px. The "Was this useful?" row lands far below the fold, so ratings never get collected.
- **Principle:** an app shell is a fixed viewport (`100dvh`); only *panels* scroll, never the page. Figma, Excalidraw,
  draw.io, Lucid all work this way.
- **Fix:** `body` → `h-dvh overflow-hidden`; workspace row `min-h-0`; each pane owns its scroll.

### 2. No fit-to-screen / zoom / pan on the canvas — `fixed (feat/app-shell-layout)`
- Diagram shows at native size. A big diagram can't be seen as a whole; the only zoom is a full-screen modal that
  also can't zoom in.
- **Principle:** *overview first, zoom and filter, then details on demand* (Shneiderman). Default to "fit", let the user
  zoom in.
- **Fix:** canvas viewport with fit-to-view on load, wheel/pinch zoom, drag-to-pan, a small zoom control
  (− 100% + / Fit), keyboard `0` = fit, `+`/`-`.

### 3. Toolbar and rating aren't anchored — `fixed (feat/app-shell-layout)`
- PNG/SVG/Iterate/New live inside the scrolling area; rating row sits under the image.
- **Fix:** toolbar pinned at the top of the canvas pane (or a floating bottom bar like Figma); rating as a small
  floating pill on the canvas.

## P1 — layout and responsiveness

### 4. Three panes wrap instead of resizing — `fixed (feat/app-shell-layout)`
- `flex-wrap` + flex-basis means at 1024px the code panel drops *below* the canvas instead of collapsing.
- **Fix:** CSS grid with explicit columns; code panel becomes a collapsible drawer/tab under ~1280px.

### 5. Mobile: diagram starts at y≈592 of 812 — `fixed (feat/app-shell-layout)`
- After generating, only ~220px of the diagram is visible; the prompt and templates sit above it.
- **Fix:** on mobile, after generate, switch to a Diagram view (tabs: Prompt / Diagram / Code) or auto-scroll to it.

### 6. Sidebar doesn't own its scroll — `fixed (feat/app-shell-layout)`
- History is capped at `max-h-72` instead of filling the remaining sidebar height.

## P2 — polish and identity

### 7. No visual identity — `open`
- Generic SaaS blue (#2558e8) + grey. Nothing memorable; looks like a template.
- Candidate palette (from an Instagram reel): navy `#14213D`, cream `#F4EDE0`, coral `#FF6B5B`. Contrast check below.

### 8. Loading state is a grey shimmer box — `open`
- Generation takes several seconds with no sense of progress. Show staged steps
  ("Understanding prompt → Picking icons → Rendering") and keep the previous diagram visible underneath.

### 9. Mixed visual languages — `open`
- Amber/orange gradient for PRO, blue for primary, black for secondary, emoji 👍👎. Too many accents.

### 10. Dark mode can't follow the OS — `open`
- Light is forced by default (decision from 2026-10-05). Fine, but `prefers-color-scheme` users get a flash of light.

### 11. Toasts pile up over the toolbar on phones — `open`
- Generate in mock mode shows 3 toasts at once ("mock mode", "generated", "edit your prompt") stacked at top-right,
  covering PNG/SVG on a 375px screen. Success toasts are also redundant when the diagram itself appears.
- **Fix:** one toast at a time, bottom-centre above the tab bar on phones; drop "Diagram generated successfully".

### 12. Local mock mode is stale — `open`
- `js/mock.js` returns `{puml}` but `app.js` reads `result.code` / `result.image`, so localhost generate shows an empty
  diagram. Makes UI testing harder than it should be.

## Palette contrast check (WCAG AA = 4.5:1 for body text, 3:1 for large text / UI)

| Pair | Ratio | Verdict |
|---|---|---|
| Navy text on cream | 13.7 | Great — main text |
| Cream text on navy | 13.7 | Great — dark mode / header |
| Navy text on coral | 5.7 | OK — coral buttons with navy label |
| Coral on navy | 5.7 | OK — coral accents in dark mode |
| **White on coral** | **2.8** | **Fails** — don't put white text on #FF6B5B |
| **Coral text on cream** | **2.4** | **Fails** — coral can't be link/text color on cream |
| White on `#C8372D` (deep coral) | 5.2 | OK — use for primary button if label must be white |
| `#C8372D` text on cream | 4.46 | Borderline — fine for large/bold, not small text |

Takeaway: coral is an **accent fill**, not a text color. Use navy-on-coral buttons, or a darker coral for text.
