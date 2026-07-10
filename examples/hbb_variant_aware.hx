# Helix — variant-aware knockout (needs network). `variant_source: ensembl` flags
# known population variants overlapping each guide; `avoid: [common_variant(>=0.01)]`
# rejects any guide with a common SNP in its seed/PAM (which would fail in carriers).

helix "HBB_KO_variant_aware" {
  organism: human(GRCh38)
  cell_line: HEK293T

  target: gene(HBB) { goal: knockout }

  strategy { modality: crispr_ko; enzyme: SpCas9 }

  constraints {
    on_target.min_efficiency: 0.4
    off_target.max_cfd: 0.2
    guides.count: 3
    avoid: [ homopolymer(>=4), common_variant(>=0.01) ]
  }

  simulate {
    sequence_provider: ensembl
    on_target: heuristic_gc
    off_target: mock_seed
    repair_outcome: mock_indel
    variant_source: ensembl
  }

  deliver: rnp
  validate: amplicon_seq
}
