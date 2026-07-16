# Product

## Register

product

## Platform

web

## Users

Helix's interface serves two kinds of human users, weighted equally, and the design must never optimize for one at the other's expense. **Bench scientists** work at the wet lab: they run an edit, then read the compiled protocol, the ranked guides, the order-ready oligos, the safety and delivery recommendation — they need the result legible and trustworthy without a manual. **Computational biologists** author and tune specs: they write the DSL, set constraints, swap backends, and compare runs — they need density, control, and precise feedback when the compiler solves or reports infeasibility. A tradeoff between ease-of-use and depth is resolved by serving both, not by picking a side: progressive disclosure, sane defaults with full override, and drill-downs that reward the power user without taxing the reader.

A third consumer drives the same workflow without touching the UI: **LLM agents** compile through the MCP server. They are not a UI audience, but they are why the spec→compile boundary must stay visible and auditable on screen — the trail a human reads is the trail an agent is held to.

## Product Purpose

Helix turns a gene-editing experiment into a reviewable, reproducible artifact. A user writes a small declarative spec (the *intent*); a deterministic compiler — assisted by narrowly-scoped LLM agents that may only emit or edit the spec — resolves it into a fully provenance-stamped design: ranked guides or pegRNAs, protein-consequence calls, feasibility against first-class constraints, safety screening, a delivery recommendation, and order-ready oligos. Success is a design a scientist can trust, diff, version in git, and re-run to the same result — and that any reviewer, human or agent, can audit end to end.

## Positioning

The same audit trail that protects a human protects an agent. Helix draws one hard trust boundary — agents and authors may only touch the spec; only the deterministic compiler produces the design — and every screen reinforces that boundary as the source of reproducibility and reviewability. That auditable spec→compile split, identical for a person and a machine, is the thing Helix does that a chat-based gene-editing tool cannot.

## Brand Personality

Precise, trustworthy, rigorous. The voice is that of a well-made scientific instrument: calm, exact, and quietly authoritative, never hyped. It states what it knows and, just as plainly, what it doesn't — a heuristic is labelled a heuristic, a real model is named, infeasibility is reported rather than hidden. Confidence comes from being right and legible, not from decoration.

## Anti-references

Helix should not look or feel like any of these:

- **A flashy AI-chat SaaS** — no gradient hero, no chatbot-first layout, no "magic AI" framing or hype copy. Helix is a deterministic compiler with agents on a leash, not a chat box that returns a one-off answer.
- **A dated enterprise bioinformatics UI** — no cluttered, gray, 2010-era lab-software density; no undifferentiated wall of tables with no hierarchy. Information is dense where it must be, but always ordered and legible.
- **A generic dev-tool dashboard** — no default dark-terminal "devtool" aesthetic applied by reflex. The design belongs to its scientific domain, not to a template.

## Design Principles

- **The spec is the artifact.** Every screen reinforces that the design is reviewable, diffable, reproducible source — not an ephemeral answer. Provenance, versioning, and re-runnability are visible, not buried.
- **Honest instruments.** Never overstate certainty. A real model, a heuristic, and a mock are clearly distinguished on screen; feasibility, safety, and confidence are reported plainly, including when the answer is "no" or "unknown."
- **Serve the bench and the terminal.** The same interface must work for a wet-lab scientist reading a protocol and a computational biologist tuning constraints. Defaults are sane, depth is one drill-down away, and neither user is taxed for the other's needs.
- **The trust boundary is a feature, not plumbing.** The spec→compile split that governs both humans and agents is surfaced as a first-class concept, because auditability is the product's core promise.
- **Rigor over flash.** Precision, legibility, and correctness beat visual spectacle. When a choice is between looking impressive and being unambiguous, be unambiguous.

## Accessibility & Inclusion

Target **WCAG 2.1 AA** across the app: body text ≥4.5:1 contrast (large text ≥3:1), visible focus indicators, and AA compliance as the baseline for every new surface. Additional non-negotiables, driven by the domain:

- **Color-blind-safe status encoding.** The UI leans on green / amber / red for pass / warn / fail (guides, checks, consequence calls, model readiness). Status must never be conveyed by color alone — always pair it with an icon, label, or shape so a color-blind scientist reads the same result.
- **Full reduced-motion support.** Every animation — spinners, reveals, and the interactive 3D helix / Cas9 complex viewer — has a `prefers-reduced-motion: reduce` alternative (crossfade or instant), and motion never gates content visibility.
- **Keyboard-navigable throughout.** The spec editor, result tables, tabs, and the 3D viewer controls are all fully operable by keyboard, with a sensible focus order.
