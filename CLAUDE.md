# CLAUDE.md

## Design Context

Helix's design system is captured in two root files — read them before any UI work:

- **[PRODUCT.md](PRODUCT.md)** — strategy: register (`product`), platform (`web`), users, purpose, positioning, brand personality, anti-references, accessibility. Answers *who / what / why*.
- **[DESIGN.md](DESIGN.md)** — the visual system: color tokens, typography, elevation, components, and do's/don'ts. Answers *how it looks*. The YAML frontmatter is normative.

**The one-paragraph frame:** Helix is a precise **"scientific instrument"** UI for reproducible gene-editing design, serving bench scientists and computational biologists equally. Feel: *precise · trustworthy · rigorous*. One signature indigo (`#5b53e0`) on a cool paper canvas; monospace is data; green/amber/red mean status only. Accessibility is non-negotiable: **WCAG 2.1 AA, color-blind-safe status encoding, full reduced-motion, keyboard-navigable throughout**. It must never look like a flashy AI-chat SaaS, a dated enterprise bioinformatics UI, or a generic dev-tool dashboard.

Design/UI work is powered by the `impeccable` skill (`/impeccable <command>`, e.g. `critique`, `audit`, `polish`, `live`). A `PostToolUse` hook auto-runs the design detector after edits to UI files; toggle it with `/impeccable hooks off`.
