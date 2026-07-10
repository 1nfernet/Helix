# Helix — C-to-G base edit (CGBE). A glycosylase base editor converts a target C
# to G within the protospacer window (positions 4-8), like CBE/ABE but a transversion.

helix "TP53_CGBE_HEK293" {
  organism: human(GRCh38)
  cell_line: HEK293T

  target: gene(TP53) {
    sequence: "ACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGT"
  }

  strategy {
    modality: base_edit
    enzyme:   SpCas9
    editor:   CGBE          # C -> G (glycosylase base editor); CBE = C->T, ABE = A->G
  }

  constraints {
    on_target.min_efficiency: 0.0
    guides.count: 3
    avoid: [ homopolymer(>=5) ]
  }

  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed }
  deliver: rnp
  validate: amplicon_seq
}
