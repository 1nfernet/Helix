# Helix — CRISPRa: dCas9-VPR activates a gene, no cut. Guides are scored by position
# relative to the TSS (strongest in the upstream promoter, ~ -400 to -50 bp).

helix "TP53_CRISPRa" {
  organism: human(GRCh38)
  cell_line: HEK293T

  target: gene(TP53) {
    sequence: "ACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGT"
    tss: 130                # activation guides sit upstream of this
  }

  strategy { modality: crispra }   # enzyme is always dCas9

  constraints {
    on_target.min_efficiency: 0.0
    off_target.max_cfd: 0.3
    guides.count: 3
    avoid: [ homopolymer(>=5) ]
  }

  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed }
  deliver: lnp
  validate: amplicon_seq
}
