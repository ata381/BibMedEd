# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** BibMedEd
**Category:** Research tool — bibliometrics for medical education
**Implemented in:** `bibmeded/frontend/src/app/globals.css` (Tailwind v4 `@theme` tokens). This file and that file must stay in sync; the CSS is the runtime source of truth.

---

## Direction: journal editorial

The interface should read like a well-set journal article, not a SaaS dashboard: serif headlines and numerals, hairline rules instead of card piles, small-caps eyebrows, figures with captions, one teal accent used semantically. Audience: medical educators, librarians, bibliometricians — people who value clarity, trust, and dense-but-legible data.

The one thing a visitor should remember: *this tool is built by people who read papers.*

## Global Rules

### Color Palette

Hue family carried over from the original teal + health-green brief; every value below was re-derived so text/background pairings pass WCAG 2.2 AA (4.5:1 text, 3:1 UI/graphics). Ratios were verified with a script; the `#0891B2` primary of the original brief (3.6:1 on white) is retained only as `secondary`, for non-text marks.

| Role | Light | Dark | CSS Variable | Notes |
|------|-------|------|--------------|-------|
| Surface (paper) | `#F5F7F6` | `#0B1414` | `--color-surface` | body |
| Surface raised | `#FFFFFF` | `#122020` | `--color-surface-raised` | cards, inputs |
| Surface sunken | `#E9EEEC` | `#070F0F` | `--color-surface-sunken` | sidebar, chart wells |
| On surface (ink) | `#12201F` | `#E5EDEB` | `--color-on-surface` | 15.6:1 / 15.7:1 |
| On surface muted | `#3D4F4D` | `#B4C3C1` | `--color-on-surface-muted` | 8.1:1 / 10.2:1 |
| On surface subtle | `#5B6D6B` | `#93A6A3` | `--color-on-surface-subtle` | 5.1:1 / 7.3:1 — smallest text |
| Ink panel | `#12201F` | `#E5EDEB` | `--color-ink` / `--color-on-ink` | primary buttons, query preview, toasts |
| Primary | `#0B6B7C` | `#63D3E3` | `--color-primary` | links, active nav, 5.7:1 / 10.6:1 |
| Primary container | `#D3EFF3` | `#0E4550` | `--color-primary-container` | with `--color-on-primary-container` |
| Secondary (graphic only) | `#0891B2` | `#22D3EE` | `--color-secondary` | 3.7:1 — never body text |
| Accent / included | `#15803D` | `#6BD996` | `--color-accent` | PRISMA "included", success |
| Warning | `#8A4B00` | `#F6BC63` | `--color-warning` | manual exclusions, cap notice |
| Danger / excluded | `#B42318` | `#FF9089` | `--color-danger` | duplicates, excluded |
| Outline strong | `#6B7E7C` | `#7F9391` | `--color-outline-strong` | input borders, 4.3:1 / 5.2:1 |
| Divider | `#DDE5E3` | `#1F3130` | `--color-divider` | hairline rules (decorative) |
| Focus ring | `#08525F` | `#8FE2EE` | `--color-focus-ring` | 2px, offset 2px |
| Code surface | `#0E1A1B` / `#A9EDF2` | same | `--color-code-bg` / `--color-code-fg` | 13.6:1; `--color-code-muted` 8.8:1 for placeholders |
| Chart ramp | `--color-chart-1…5` | | | steps 3–5 pass 3:1 on raised surfaces |

### Typography

- **Display (headings, numerals, figure captions):** Crimson Pro, variable, weight 600 for headings, italic for captions and journal names. Loaded via `next/font/google`, self-hosted at build time.
- **Body / UI:** Atkinson Hyperlegible Next, variable. Chosen for its low-vision legibility research; 16px body, 13px minimum for UI text, 11px only for uppercase eyebrows.
- **Mono (queries, DOIs, code):** system stack (`ui-monospace, Cascadia Code, SF Mono, Menlo, Consolas`).
- No icon fonts. Icons are inline SVG from `src/components/ui/icon.tsx` so the UI renders offline.

Utilities: `.eyebrow` (small-caps label), `.numeral` (serif tabular figure), `.rule-t` / `.rule-b` (hairlines), `.paper` (grain + top wash).

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` | Tight gaps |
| `--space-sm` | `8px` | Icon gaps, inline spacing |
| `--space-md` | `16px` | Standard padding |
| `--space-lg` | `24px` | Section padding |
| `--space-xl` | `32px` | Large gaps |
| `--space-2xl` | `48px` | Section margins |
| `--space-3xl` | `64px` | Hero padding |

Rhythm is intentionally uneven: page headers get generous space below their rule; list rows are tight (20–24px) so dense data stays scannable.

### Radius, Shadow, Motion

- Radius is restrained: `--radius-md: 6px` for controls, `--radius-lg: 10px` for cards. Pills only for the theme toggle / progress bar.
- Shadows `--shadow-sm…xl`; cards default to no shadow (a hairline border), lifting to `--shadow-md` on hover for interactive rows.
- Motion: `--duration-fast: 150ms` for colour, `--duration-base: 220ms` for layout, `--duration-slow: 360ms` for the landing reveal (`.rise`, `.draw`). All animation collapses under `prefers-reduced-motion`; the force graph settles synchronously instead of animating.

---

## Component Specs

- **Button** (`ui/button.tsx`): `primary` = ink on paper (inverts in dark), `secondary` = primary container, `outline`, `ghost`, `danger`. `ButtonLink` for navigation — never nest `<button>` in `<a>`.
- **Card** (`ui/card.tsx`): raised / sunken / ink tones; `CardHeader` takes an `eyebrow` ("Figure 1", "Table 2") so dashboard panels read as numbered figures.
- **PageHeader** (`ui/page-header.tsx`): eyebrow → serif h1 → lede → bottom rule; `aside` slot for the page's primary action.
- **Stat / StatRow** (`ui/stat.tsx`): journal-table KPI strip — small-caps label, serif numeral, footnote; rows are ruled, not boxed.
- **Tabs** (`ui/tabs.tsx`): underline tabs on a hairline; full ARIA tablist with arrow/Home/End keys.
- **Charts** (`charts/`): `BarChart` (SVG with gridlines, value labels, sr-only data table) and `RankedBars` (ranked list with inline proportional bar). `ForceGraph` adds keyboard zoom controls, neighbour highlighting, a legend, and an sr-only top-nodes list.
- **Forms**: `.field` class — 1px `outline-strong` border (3:1), primary border + focus ring on focus, `.field-code` variant for query editors.

---

## Anti-Patterns (Do NOT Use)

- ❌ Emojis or icon fonts as icons — inline SVG only
- ❌ Card grids with uniform padding for lists of data — use ruled rows
- ❌ Raw Tailwind palette colours (`text-red-600`) — tokens only
- ❌ Hover-only information (tooltips) with no keyboard/text equivalent
- ❌ `<button>` inside `<a>` or vice versa
- ❌ Text below 13px other than uppercase eyebrows
- ❌ Layout-shifting hovers (scale transforms)
- ❌ Instant state changes — transition 150–360ms
- ❌ Invisible focus states

---

## Pre-Delivery Checklist

- [ ] No icon fonts; all icons from `ui/icon.tsx`
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with transitions (150–360ms)
- [ ] Light and dark: text contrast 4.5:1, UI borders 3:1 (see table)
- [ ] Focus visible on every control (2px ring, 2px offset)
- [ ] `prefers-reduced-motion` respected
- [ ] Heading order h1 → h2 → h3 with no skips
- [ ] Every chart has an `aria-label` and an sr-only data equivalent
- [ ] Responsive at 375, 768, 1024, 1440; no horizontal scroll
- [ ] `npm run lint && npx tsc --noEmit && npm run build && npm run test:e2e` pass
