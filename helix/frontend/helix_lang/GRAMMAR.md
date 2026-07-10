# The Helix grammar

Helix source (`.hx`) is a small declarative language for describing one
gene-editing experiment. It compiles to the exact same `ExperimentSpec` IR as the
YAML frontend, so anything expressible in one is expressible in the other.

## Example

```hx
helix "TP53_KO_HEK293" {
  organism: human(GRCh38)
  cell_line: HEK293T

  target: gene(TP53) {
    goal: knockout
    region: exon(2..4)
    sequence: "ACGT..."        # optional; omit to resolve via a sequence provider
  }

  strategy { modality: crispr_ko; enzyme: auto }

  constraints {
    on_target.min_efficiency: 0.5
    off_target.max_cfd: 0.2
    guides.count: 3
    avoid: [ homopolymer(>=4), restriction_site(BsaI) ]
  }

  simulate {
    sequence_provider: ensembl
    on_target: heuristic_gc
    off_target: mock_seed
    repair_outcome: mock_indel
  }

  deliver: rnp
  validate: amplicon_seq
}
```

## Grammar (EBNF)

```ebnf
program    = "helix" STRING block ;
block      = "{" statement* "}" ;
statement  = key ( ":" value block? | block ) ";"? ;
key        = IDENT ( "." IDENT )* ;
value      = STRING | NUMBER | BOOL | call | list | IDENT ;
call       = IDENT "(" ( arg ( "," arg )* ","? )? ")" ;
arg        = CMP NUMBER | value ( ".." NUMBER )? ;
list       = "[" ( value ( "," value )* ","? )? "]" ;
```

* `STRING` — double-quoted. `NUMBER` — integer or decimal. `BOOL` — `true`/`false`.
* `IDENT` — `[A-Za-z_][A-Za-z0-9_]*` (covers `HEK293T`, `crispr_ko`, `SpCas9`).
* `CMP` — one of `>= <= > < =`. `..` denotes a range (`exon(2..4)`).
* `#` starts a comment to end of line. Newlines and `;` are insignificant separators.

## Surface → IR mapping

| Surface | IR field |
|---|---|
| `helix "N" { ... }` | `name` |
| `organism: human(GRCh38)` | `organism`, `genome_build` |
| `target: gene(SYM) { ... }` | `target.gene` + nested `goal`/`region`/`sequence`/`edit` |
| `region: exon(2..4)` | `target.region = "exon 2-4"` (hint; not yet enforced) |
| `edit: "C>T @ 50"` | `target.edit` (prime edit / HDR knock-in; sub `>`, ins `->`, del `>-`) |
| `delete: "40..95"` | `target.delete` (dual-cut deletion span, 1-based inclusive) |
| `tss: 40` | `target.tss` (transcription start site for CRISPRi/a) |
| `frame: 0` | `target.frame` (reading-frame phase of window pos 0; enables protein-consequence calls + synonymous HDR PAM-blocking) |
| `strategy { modality: …; enzyme: …; editor: …; donor: … }` | `strategy.*` — `modality` ∈ {crispr_ko, base_edit, prime_edit, hdr, deletion, crispri, crispra}; `enzyme` ∈ {auto, SpCas9, SaCas9, Cas12a, SpG, SpRY, Cas9-NG} (dCas9 is implied by crispri/a); `editor` ∈ {CBE, ABE, CGBE}; `donor` ∈ {ssodn, dsdna} |
| `on_target.min_efficiency: x` | `constraints.on_target_min_efficiency` |
| `off_target.max_cfd: x` | `constraints.off_target_max_cfd` |
| `guides.count: n` | `constraints.guides_count` |
| `gc.min: 0.4` / `gc.max: 0.7` | `constraints.gc_min` / `gc_max` — spacer GC window |
| `avoid: [homopolymer(>=4)]` | `constraints.max_homopolymer = 4` |
| `avoid: [self_complementary(>=8)]` | `constraints.max_self_complementarity = 8` — hairpin filter |
| `avoid: [common_variant(>=0.01)]` | `constraints.max_variant_freq = 0.01` — reject a seed/PAM SNP at ≥ this frequency |
| `avoid: [restriction_site(BsaI)]` | `constraints.avoid_restriction_sites += ["BsaI"]` |
| `simulate { variant_source: ensembl }` | flag population variants in the seed/PAM (needs a database-resolved target) |
| `profile: strict` | preset constraint/simulate defaults (`strict` / `lenient` / `screen` / `quick`); any explicit setting overrides the preset |
| `simulate { ... }` | `simulate.*` (adapter registry keys) |
| `deliver: rnp` | `deliver` |
| `validate: amplicon_seq` | `validate_with` |

## Implementation

`lexer.py` (scanner) → `parser.py` (recursive descent → AST) → `transform.py`
(AST → IR dict) → `spec_from_dict` (Pydantic validation). Errors carry
`(line, col)` and a caret snippet. No third-party dependencies.

Not yet in the grammar (Phase 3): adapter composition (`off_target: a + cfd`),
multiple targets per experiment, exon-precise region resolution.
