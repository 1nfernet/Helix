# Helix — knockout with SpRY, an engineered near-PAMless SpCas9 (NRN PAM).
# Relaxed PAMs open up sites SpCas9 (NGG) can't reach — many more candidate guides.

helix "TP53_KO_SpRY" {
  organism: human(GRCh38)
  cell_line: HEK293T

  target: gene(TP53) {
    goal: knockout
    sequence: "ACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGT"
  }

  strategy {
    modality: crispr_ko
    enzyme:   SpRY          # NRN PAM; also SpG (NGN), Cas9-NG (NG)
  }

  constraints {
    on_target.min_efficiency: 0.0
    off_target.max_cfd: 0.3
    guides.count: 3
    avoid: [ homopolymer(>=5) ]
  }

  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel }
  deliver: rnp
  validate: amplicon_seq
}
