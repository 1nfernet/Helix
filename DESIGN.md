---
name: Helix
description: A precise scientific-instrument UI for reproducible gene-editing design.
colors:
  helix-indigo: "#5b53e0"
  indigo-deep: "#4840c4"
  indigo-wash: "#ecebfb"
  cool-paper: "#f5f6f9"
  surface-white: "#ffffff"
  cool-inset: "#eef1f6"
  ink: "#12151f"
  ink-secondary: "#525863"
  ink-muted: "#666d76"
  hairline: "#e3e7ee"
  hairline-strong: "#ccd2dd"
  signal-green: "#0b7a5d"
  green-wash: "#e0f2ec"
  green-line: "#b7ddcd"
  signal-amber: "#8a6011"
  amber-wash: "#f6ecd5"
  amber-line: "#e6d2a4"
  signal-red: "#bd382e"
  red-wash: "#fbe6e3"
  red-line: "#f2c3bb"
  steel: "#4d6c7a"
  base-a: "#2f7d5f"
  base-t: "#b8553a"
  base-g: "#3768ab"
  base-c: "#a87a24"
  base-n: "#7c828c"
typography:
  display:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "23px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  body-sm:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.04em"
  micro:
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.04em"
  mono:
    fontFamily: "ui-monospace, 'SF Mono', 'SFMono-Regular', Menlo, Consolas, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: "0.02em"
rounded:
  xs: "4px"
  sm: "7px"
  md: "10px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "18px"
  xl: "22px"
  xxl: "30px"
components:
  button-primary:
    backgroundColor: "{colors.helix-indigo}"
    textColor: "{colors.surface-white}"
    rounded: "{rounded.sm}"
    padding: "9px 18px"
  button-primary-hover:
    backgroundColor: "{colors.indigo-deep}"
  panel:
    backgroundColor: "{colors.surface-white}"
    rounded: "{rounded.md}"
  input:
    backgroundColor: "{colors.cool-inset}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "7px 10px"
  nav-item-active:
    backgroundColor: "{colors.indigo-wash}"
    textColor: "{colors.indigo-deep}"
    rounded: "{rounded.sm}"
    padding: "9px 11px"
  badge-ok:
    backgroundColor: "{colors.green-wash}"
    textColor: "{colors.signal-green}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  badge-warn:
    backgroundColor: "{colors.amber-wash}"
    textColor: "{colors.signal-amber}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  badge-danger:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.signal-red}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  badge-neutral:
    backgroundColor: "{colors.cool-inset}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
---

# Design System: Helix

## 1. Overview

**Creative North Star: "The Scientific Instrument"**

Helix looks and behaves like a precision instrument on a lab bench: calm, exact, and quietly authoritative. The canvas is a cool near-white paper (`#f5f6f9`) rather than pure white or a warm cream, so panels of `#ffffff` lift off it as clean readable surfaces. A single signature indigo (`#5b53e0`) carries identity and interaction — it is the one saturated voice in an otherwise neutral field, and its restraint is what makes it read as considered rather than decorated. Data — sequences, scores, provenance, protocol text — is set in monospace and treated as first-class evidence, because in this product the numbers *are* the design.

The system is dense where the work is dense (ranked guide tables, drill-downs, order oligos) and generous where the reader needs to breathe (empty states, section rhythm, the 3D helix viewport). It resolves the tension between the bench scientist reading a result and the computational biologist tuning a spec through progressive disclosure: sane surfaces up front, exact detail one caret-click deeper. Nothing shouts. The largest type on any screen is ~23px; there is no hero, no gradient, no marketing gesture.

It explicitly rejects three looks. It is **not a flashy AI-chat SaaS** — no gradient hero, no chatbot-first layout, no "magic AI" framing. It is **not a dated enterprise bioinformatics UI** — no gray, cluttered, undifferentiated wall of tables. And it is **not a generic dev-tool dashboard** — no reflexive dark-terminal aesthetic pasted over a scientific domain. Helix belongs to its field.

**Key Characteristics:**
- Cool paper canvas with white surfaces lifted by 1px hairlines, not heavy shadow.
- One signature indigo; a disciplined green / amber / red trio reserved for status only.
- Monospace treated as data, geometric-sans (Inter) for everything human-readable.
- Dense, ordered information with legible hierarchy — never a flat table dump.
- Restraint over spectacle: no gradients, no glass, no oversized type.

## 2. Colors

A cool, neutral field with one saturated indigo voice and a strict semantic trio for status.

### Primary
- **Helix Indigo** (`#5b53e0`): The signature. Primary buttons, active nav, focus rings, links, meters/progress fills, the PAM highlight in sequences, and the caret. The one saturated color on the screen — its rarity is the point.
- **Indigo Deep** (`#4840c4`): The pressed/hover state of the indigo and the color of active-tab / active-nav text. Also the DSL keyword color in the code editor.
- **Indigo Wash** (`#ecebfb`): The soft indigo tint behind active nav items, selected/differing compare rows, and inline-edited sequence footprints. Never used for text.

### Secondary
- **Steel** (`#4d6c7a`): The second categorical color, used *only* to distinguish comparison slot "B" from indigo's slot "A" in the compare view, and as the `t-func` accent in code. It is a data-differentiation color, not a brand color; do not promote it to general use.

### Tertiary — Status trio (semantic only)
Each hue clears AA as text on **both** Surface White and its own wash; `-line` is the chip border.
- **Signal Green** (`#0b7a5d`) on **Green Wash** (`#e0f2ec`), border **Green Line** (`#b7ddcd`): pass / ok / real-model / synonymous edit / ready.
- **Signal Amber** (`#8a6011`) on **Amber Wash** (`#f6ecd5`), border **Amber Line** (`#e6d2a4`): warn / caution / missense / needs-setup / demo mode.
- **Signal Red** (`#bd382e`) on **Red Wash** (`#fbe6e3`), border **Red Line** (`#f2c3bb`): fail / danger / premature-STOP / frameshift / error.

### Categorical — the nucleotide palette
The one sanctioned exception to the rules below, because base identity is genuinely categorical and the domain genuinely needs four telling-apart-able hues:
- **Base A** (`#2f7d5f`) · **Base T** (`#b8553a`) · **Base G** (`#3768ab`) · **Base C** (`#a87a24`) · **Base N** (`#7c828c`)

Scope is hard-bounded: **base identity in the sequence and 3D views, nowhere else** — never status, never chrome, never a category that isn't a nucleotide. The hues are separated along the blue↔orange axis (the axis that survives red-green color blindness), and every use pairs the color with its letter, so hue is reinforcement and never the sole encoding. The Cas9 complex viewer reuses three of these same hues for protein / RNA / DNA rather than opening a fifth palette; the two axes never share a screen. Defined once in `frontend/src/palette.ts` and derived for both CSS and WebGL — a legend that disagrees with the picture beside it is a bug.

### Neutral
- **Cool Paper** (`#f5f6f9`): The app background canvas.
- **Surface White** (`#ffffff`): Panels, cards, popovers, the active segmented-control thumb.
- **Cool Inset** (`#eef1f6`): Recessed fills — code editor background, muted chips, table selection, inputs, protocol `<pre>`.
- **Ink** (`#12151f`): Primary text.
- **Ink Secondary** (`#525863`): Secondary text, labels, nav rest state.
- **Ink Muted** (`#666d76`): Tertiary text, hints, metadata, rank numbers, placeholders' non-input siblings.
- **Hairline** (`#e3e7ee`) / **Hairline Strong** (`#ccd2dd`): Borders and dividers; the strong variant for hover/focus emphasis on inputs.

### Named Rules
**The One Indigo Rule.** Exactly one saturated hue carries the brand: Helix Indigo. Everything else is neutral, a status signal, or the nucleotide palette. If a second saturated color appears outside comparison slot "B" (Steel) and base identity, it is a bug.

**The Status-Is-Earned Rule.** Green, amber, and red are reserved for *result state* — never for decoration, emphasis, or category. A red element on a Helix screen always means something failed or is dangerous. (A green *base* is not a passing base — the nucleotide palette is a separate vocabulary that never appears in chrome.)

**The Contrast-Over-Fade Rule.** Every ink step clears WCAG AA on all three neutral surfaces, including Ink Muted on Cool Inset — the darkest ground it sits on. That compresses the muted→secondary step, so **hierarchy is carried by size and weight, not by fading text toward the background.** Never dim a container with `opacity` to say "inactive": it scales every label inside below AA. Recede it a tone instead, and say the state in words.

## 3. Typography

**Display / Body Font:** Inter (with `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`)
**Data / Mono Font:** `ui-monospace, "SF Mono", "SFMono-Regular", Menlo, Consolas, monospace`

**Character:** One geometric-humanist sans (Inter) does all human-readable work across weights, paired on a hard contrast axis with a monospace stack that carries all machine data — sequences, scores, keys, protocol. There is deliberately **no** editorial serif: an earlier version used one and it read as generic-editorial; Helix reads as a modern instrument instead. The pairing logic is human-vs-machine, not decorative.

### Hierarchy

Eight steps, and only eight. A dense instrument needs more rungs than a marketing page, but the ramp had drifted to seventeen sizes between 9px and 23px — eight of them crowded into a 3.5px band, which is accretion, not a system. If a new size seems necessary, one of these is wrong.

- **Display** (600, 23px, line-height 1.2, `-0.01em`): Page/mode titles in the topbar and the result summary title. The largest type in the app.
- **Headline** (600, 20px, 1.2): Section stat values, summary metrics, the wordmark, empty-state headings — the at-a-glance numbers.
- **Title** (600, 15px, 1.3): Sub-section headings, compare slot names.
- **Body** (400, 14px, 1.55): Default reading size. Cap prose at 65–75ch.
- **Body Small** (400, 13px, 1.5): The dense-UI size — nav, buttons, controls, table rows, hints.
- **Mono / Data** (400, 12.5px, 1.7, `0.02em`): Sequences, scores, oligos, provenance keys, protocol text, the code editor.
- **Label** (600, 12px, `0.04em`, UPPERCASE): Section labels, table headers, panel headers. Tracked, quiet, structural.
- **Micro** (600, 11px, `0.04em`, UPPERCASE): Tags, chips, gutter numbers, badge text. The floor — nothing is smaller.

### Named Rules
**The Data-Is-Mono Rule.** Any machine-generated or literally-precise value — a spacer, a score, a locus, a provenance hash, a DSL token — is set in the mono family. If a scientist would copy it into a terminal or an order form, it is monospace.

**The Quiet-Label Rule.** Structural labels are 12px, uppercase, tracked `0.04em`, and `ink-muted` — present but never competing with content. Labels orient; they do not decorate.

## 4. Elevation

The system is **flat by default, defined by borders, not shadow.** Depth comes from a three-tone neutral stack — Cool Paper canvas → Surface White panels → Cool Inset recesses — bounded by 1px hairlines. There is exactly one shadow token, a whisper-soft ambient double-layer, applied to lifted surfaces (panels, the active segmented-control thumb, active meters). It signals "this floats slightly," never "this is dramatic."

### Shadow Vocabulary
- **Ambient Soft** (`box-shadow: 0 1px 2px rgba(18,21,31,0.05), 0 6px 20px rgba(18,21,31,0.05)`): The only elevation. Panels and the active seg-control thumb. Both layers at 5% opacity — barely there on purpose.

### Corner scale
Four steps, no others: **xs 4px** (inline sequence highlights, nested seg thumbs, micro tags) · **sm 7px** (buttons, inputs, controls, small cards) · **md 10px** (panels and cards) · **pill 999px** (badges, chips, meters).

### Named Rules
**The Border-Not-Shadow Rule.** Surfaces are separated by 1px hairlines and tonal steps, not by stacked shadows. If a surface needs to read as distinct, reach for a hairline or the next neutral tone before you reach for elevation.

## 5. Components

### Buttons
- **Shape:** Gently rounded (7px, `rounded.sm`).
- **Primary:** Solid Helix Indigo (`#5b53e0`) on white text, padding `9px 18px`, weight 550. The one filled, saturated control on screen.
- **Hover / Focus:** Background shifts to Indigo Deep (`#4840c4`) over a 0.12s ease; disabled drops to 55% opacity. Focus is a visible indigo ring, never removed.
- **Link button:** Indigo text, no fill, underline on hover — for tertiary actions.

### Segmented control (`.seg`) vs. tabs (`.rtabs`)
- **Style:** Cool Inset track, 3px inner padding; the active segment is a Surface White thumb carrying the Ambient Soft shadow. Inner radius is `rounded.xs` — the outer 7px minus the 3px track padding, which is what keeps a nested corner concentric rather than merely "also rounded".
- **Rule — the two are not interchangeable.** A `.seg` is a set of **pressed toggles** (`role="group"` + `aria-pressed`): same content, different rendering (Table · 3D helix · Cas9 complex; Helix · YAML; Haiku · Sonnet). `.rtabs` are **real tabs** (`role="tablist"`/`tab`/`tabpanel`, roving `tabIndex`, arrow-key navigation): distinct workflow sections with distinct content (Guides · Delivery · Order · Analyze). Picking the wrong one lies to assistive tech about what the control does.
- **Motion — the selection travels, it doesn't teleport.** The seg thumb (one shared `Segmented` component) and the tab's accent underline both *slide* to the newly-active option over ~240ms easeOutQuart — Apple's core selection feel, and the only "travel" motion in the app. Both animate `transform` only (no layout property), measure the live active element so they adapt to label width, and collapse to an instant move under reduced motion.

### Badges & status chips
- **Style:** Pill (999px), soft-wash background + matching signal text + `-line` border, 12px weight 550, optional 6px leading dot. Four roles: `ok` (green), `warn` (amber), `danger` (red), `neutral` (inset/secondary).
- **Rule:** A badge must never rely on color alone — it carries a text label (and often a dot/icon) so status survives color blindness. Consequence badges (silent / missense / STOP / frameshift) follow the same trio.
- **Where a dot must stand alone** (the run-history feasibility marker), **shape carries the state too**: a circle passes, a diamond warns — a distinction that survives color blindness where green-vs-amber does not — and sr-only text states it outright.

### Result-table row marker (`.row-sel`)
- **Style:** A green `✓` beside the rank, plus sr-only text ("selected by the compiler" / "passed the constraints").
- **Rule:** Which rows the compiler *chose* is the headline answer a result table exists to give. A row tint cannot carry it — it is invisible to a screen reader and easy to miss besides. Every ranked table (guides, pegRNAs, compare) uses the one `PassMark` component.

### Cards / Panels
- **Corner Style:** 10px (`rounded.md`).
- **Background:** Surface White on the Cool Paper canvas.
- **Shadow Strategy:** Ambient Soft only (see Elevation).
- **Border:** 1px Hairline; header divided by a 1px Hairline under an uppercase label.
- **Internal Padding:** 18px body; `14px 18px` header.
- **Rule:** Cards are containers of record, not decoration. **Never nest a card inside a card.**

### Inputs / Fields (`select`, `textarea`, `.ai-input`)
- **Style:** Cool Inset (or Surface White for the AI input) fill, 1px Hairline, 7px radius, padding `7px 10px`.
- **Focus:** Border shifts to Helix Indigo with a soft Indigo Wash ring (`outline: 2px var(--accent-soft)` or `box-shadow: 0 0 0 3px`). Never remove the focus indicator.

### Navigation (sidebar)
- **Style:** 208px sticky rail on Surface White; items are `ink-secondary` at rest, gain a Cool Inset hover, and go **active** with an Indigo Wash fill + Indigo Deep text at weight 500. A mono nav-badge pill shows counts.
- **Mobile:** Below 760px the rail collapses to a horizontal top bar and labels hide, leaving icons.

### Data tables (`table.data`)
- **Style:** Full-width, uppercase tracked `label` headers on a Hairline underline, 13px body rows divided by Hairlines, `tabular-nums` for all numeric columns. Selected/open rows tint Cool Inset. Rows expand in place into a drill-down (sequence with highlighted PAM, off-target table, pass/fail checks, variant flags).
- **Overflow — scroll edge, not clip.** A ranked guide table is eight dense columns and will not fit beside the spec editor on a laptop, so it scrolls horizontally inside its panel (`TableScroll`). A soft fade appears at whichever edge has more table (Apple §12) — gated on real scroll position, so a table that fits keeps its last column perfectly crisp. The page itself never scrolls sideways.

### Reveal & press (the rest of the motion budget)
- **Compile reveal:** when a design first lands it fades up 4px over ~220ms — a quiet "the run finished", not choreography. Its resting state is fully visible, so reduced motion (or a headless render) simply shows it instantly; content is never gated on the transition.
- **Press:** the primary button scales to 0.975 on `:active` — feedback on the press itself, not the release (Apple §1).
- Everything else is a 120–160ms hover/focus/selection tint. Nothing decorative, and every animation has a `prefers-reduced-motion` collapse.

### Strength meter (`.meter`)
- **Style:** A 6px rounded track (Hairline) with an Indigo fill sized to the score — the compact inline visualization for efficiency / off-target / delivery-fit scores. Paired with a `tabular-nums` value.

### Code / Spec editor (signature component)
- **Style:** A transparent textarea over a syntax-highlight layer inside a Cool Inset frame, mono 12.5px / line-height 1.7, a muted line-number gutter, error lines tinted Red Wash with a red gutter number. Syntax theme: comments muted-italic, strings green, numbers/bools amber, keywords Indigo Deep, functions Steel, punctuation muted. The caret is Helix Indigo. This is the heart of the product — the spec as reviewable source.

## 6. Do's and Don'ts

### Do:
- **Do** keep Helix Indigo (`#5b53e0`) as the single saturated voice — primary actions, active state, focus, meters, the PAM highlight — and let neutrals carry everything else.
- **Do** set every machine value (sequences, scores, loci, provenance, DSL) in the mono family; scientists copy these into terminals and order forms.
- **Do** pair every status color with a text label and/or shape so pass/warn/fail survives color blindness (WCAG-driven, non-negotiable per PRODUCT.md).
- **Do** define surfaces with 1px hairlines and the three-tone neutral stack; reach for the single Ambient Soft shadow only for genuinely lifted panels.
- **Do** provide a visible focus ring on every interactive element and full keyboard operability across the editor, tables, tabs, and 3D controls.
- **Do** give every animation — spinners, reveals, the 3D helix/Cas9 viewer — a `prefers-reduced-motion: reduce` alternative, and never gate content visibility on a transition. **The CSS media block is not enough for the viewers:** their auto-rotate lives in a `requestAnimationFrame` loop that CSS never sees, so each viewer queries the preference itself (`frontend/src/motion.ts`) and gates its own spin.
- **Do** keep the 3D viewers fully keyboard-operable — the helix carries `tabIndex`, a base cursor on the arrow keys, Enter to place an edit, and an `aria-live` readout, because the 3D → spec round-trip is a headline feature and a mouse-only feature is a missing feature.
- **Do** use progressive disclosure (sane surface, drill-down for depth) so the bench scientist and the computational biologist are served by the same screen.

### Don't:
- **Don't** make Helix look like a **flashy AI-chat SaaS**: no gradient hero, no `background-clip: text` gradient text, no chatbot-first layout, no "magic AI" hype copy.
- **Don't** make it look like a **dated enterprise bioinformatics UI**: no gray, cluttered, undifferentiated wall of tables with no hierarchy.
- **Don't** make it a **generic dev-tool dashboard**: no reflexive dark-terminal aesthetic dropped over the scientific domain.
- **Don't** introduce a second saturated hue. Steel (`#4d6c7a`) exists *only* for comparison slot "B", and the nucleotide palette *only* for base identity; anything else saturated is a bug (The One Indigo Rule).
- **Don't** spend green / amber / red on decoration, emphasis, or category — status only (The Status-Is-Earned Rule).
- **Don't** fade a container with `opacity` to mean "inactive", or lighten text for elegance: both scale labels below AA. Recede a tone and say the state in words (The Contrast-Over-Fade Rule).
- **Don't** let colour, tint, or position be the *only* carrier of a result — selected guides, feasibility, and diffs each need a glyph, label, or shape as well.
- **Don't** add a size to the type ramp or a step to the corner scale without deleting one; eight and four respectively is the whole system.
- **Don't** nest cards, add side-stripe accent borders (>1px colored `border-left`/`right`), or stack heavy shadows to fake depth.
- **Don't** exceed ~23px for the largest type or add a hero section; Helix is an instrument, not a landing page.
- **Don't** assume the CSS reduced-motion block covers the 3D viewers — it cannot see a `requestAnimationFrame` loop. Gate the spin in JS.
