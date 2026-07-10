# Changelog

All notable changes to Helix are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-10

First public release: a declarative DSL and deterministic compiler for reproducible
gene-editing design, with a web UI, LLM agents, and an MCP server.

### Design & compiler
- **8 modalities**: CRISPR knockout, base editing (CBE/ABE/CGBE), prime editing,
  HDR knock-in, dual-cut deletion, CRISPRi, and CRISPRa.
- **Enzymes**: SpCas9, SaCas9, Cas12a, and the relaxed-PAM SpG / SpRY / Cas9-NG; dCas9
  for CRISPRi/a.
- **Constraints are first-class** — the compiler solves against them and reports
  infeasibility explicitly (guide count, on-/off-target thresholds, GC window,
  self-complementarity/hairpin, homopolymer, restriction sites, common-variant).
- **Protein-consequence awareness** (`target { frame }`): silent / missense /
  premature-STOP (base-edit iSTOP) calls, and a guaranteed-synonymous HDR PAM-block.
- **Variant-aware guides** — flag common population SNPs in the seed/PAM (Ensembl).
- **Provenance** on every design — the exact adapters/versions used, for reproducibility.

### Architecture
- **Injectable adapter seams** (sequence, on-/off-target, repair, base-/prime-edit,
  variant, folding) — swap a real tool (Cas-OFFinder, inDelphi, BE-Hive, PRIDICT,
  Ensembl/NCBI, ESMFold) for a heuristic via a spec edit, not a code change.
- **Two frontends, one IR**: the Helix grammar (hand-written lexer/parser) and YAML
  both compile to the same validated `ExperimentSpec`.

### Interfaces
- **CLI**: `helix validate | compile | author | critique | refine | serve | mcp |
  structure | analyze`.
- **Web UI** (React + Vite): syntax-highlighting spec editor, interactive 3D helix,
  Cas9-complex viewer, batch/library runs, design compare, and a design-aware Models
  page. `helix serve` now serves the built UI and the API on one origin.
- **MCP server** (`helix mcp`): drive the compiler from any agent through the
  spec → compile boundary (`helix_compile`, `helix_reference`, `helix_resolve_gene`,
  `helix_list_models`).
- **LLM agents** (optional, needs `ANTHROPIC_API_KEY`): natural-language authoring and
  adversarial design critique.

### Quality
- 230 offline tests (+1 gated network test); wheel + sdist build clean and pass
  `twine check`.
- Its own "scientific instrument" visual identity.
