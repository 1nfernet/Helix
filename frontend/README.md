# Helix frontend

An interactive UI for the Helix compiler: write a spec (Helix grammar or YAML),
compile it, and inspect the resolved design — ranked guides, off-target/outcome
metrics, feasibility, safety verdict, and provenance.

React + TypeScript (Vite), talking to the FastAPI backend (`helix serve`).

## Run

```bash
# 1. Backend (from the repo root)
pip install -e '.[web]'
helix serve                 # http://127.0.0.1:8000  (API + /docs)

# 2. Frontend (this directory)
npm install
npm run dev                 # http://localhost:5173  (proxies /api -> :8000)
```

`npm run build` type-checks (`tsc`) and produces a static bundle in `dist/`.

## Layout

- `src/api.ts` — typed client for `/api/compile` and `/api/examples`.
- `src/types.ts` — TypeScript mirror of the Helix design IR.
- `src/components/` — editor, results panel, guide/pegRNA tables, badges.
- `src/components/DeliveryCard.tsx` — delivery recommendation (RNP/plasmid/LNP/AAV) with scores.
- `src/components/DonorCard.tsx` — **HDR knock-in** donor: homology arms + highlighted insert,
  cut-to-edit distance, and whether re-cutting of the corrected allele is blocked.
- `src/components/DeletionCard.tsx` — **dual-cut deletion**: the repair junction and bp removed.
  (CRISPRi/a and relaxed-PAM enzymes reuse the guide table, with a TSS-offset / larger guide set.)
- `src/components/{BatchEditor,BatchResults}.tsx` — **Batch** mode: compile many specs, summary table.
- `src/components/LibraryEditor.tsx` — **Library** mode: one base spec + a gene list → a per-gene
  design library (each gene resolved from the database), reusing the batch summary table.
- `src/components/HistoryList.tsx` — **run history** backed by the server (`/api/runs`),
  so it persists across restarts and is shared across clients.
- `src/components/AiPanel.tsx` — **AI assist**: natural-language → spec (`/api/author`) and
  design critique with one-click apply (`/api/critique`); model toggle + per-call cost. Shown
  only when the backend reports `ai_configured` (an `ANTHROPIC_API_KEY` is set).
- `src/components/DnaHelix.tsx` — a **3D double-helix viewer** (Three.js) that renders the
  target window and highlights the guide-binding region and cut/edit site (the "Helix" tab).
  **Interactive editing** (raycast picking) rewrites the DSL `edit:` line and recompiles —
  a 3D → spec/DSL round-trip:
  - **prime editing** — *click* a base to place the edit, *drag* to sweep the position live
    (text updates as you drag; recompiles on release), *shift-click* to cycle the substituted base;
  - **base editing** — *click* a highlighted base (only the C/A a guide's window can actually
    reach are pickable, shown as glowing dots) to target it; the compiler then keeps just the
    guides that edit that base.
  A hover ring tracks the base under the cursor (grey when a base is not editable in this mode).
- `src/components/ComplexViewer.tsx` — a **3D macromolecular viewer** (NGL). It calls
  `/api/structure`, which assembles *this design's* Cas9-sgRNA-DNA complex (its guide, its
  target) via `helix.structure` and folds it when a backend (AlphaFold3/Boltz) is configured;
  otherwise it shows the composition + a reference complex (PDB 4OO8) as the geometry.
- `src/components/GuideTable.tsx` — ranked guides; **click a row** to drill down into its
  off-target sites and sequence context (guide + PAM, genomic binding footprint).
- `src/components/ComparePanel.tsx` — the **Compare** view: two saved designs side by side,
  with differing metrics highlighted.
- `src/components/GeneLookup.tsx` — resolve a gene symbol **live from Ensembl / NCBI**
  (`/api/resolve`) and insert its sequence into the spec.
- `src/components/ModelsPanel.tsx` — the **Models** view (`/api/adapters`): every database +
  simulation model Helix connects to, tagged by kind with a ready/needs-setup status.
- `ComplexViewer.tsx`'s **Fold with ESMFold** runs real protein structure prediction
  (`/api/fold`) on a SpCas9 domain and renders it coloured by pLDDT.
- `src/components/OrderCard.tsx` — **order-ready oligos** for the design (cloning oligos,
  pegRNA extensions, ssODN donors, primers) + cost + Download CSV (`/api/export`).
- `src/components/AnalyzeCard.tsx` — **close the loop**: paste/load amplicon reads → editing
  efficiency, indel spectrum, and observed-vs-predicted reconciliation (`/api/analyze`).
- `ResultsPanel.tsx` organizes the design into **workflow tabs** — Guides · Delivery · Order ·
  Analyze (adapting per modality; CRISPRi/a hide Analyze) — with an at-a-glance stat strip,
  instead of one long scroll.
- Both are lazy-loaded so Three.js / NGL stay out of the initial bundle.
- `src/styles.css` — the design system (Claude-science aesthetic).
