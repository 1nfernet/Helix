# Helix — a high-specificity knockout via a profile + guide-quality filters.
# `profile: strict` presets tight efficiency / off-target / GC / hairpin defaults;
# any constraint you write below overrides the preset. New guide-quality knobs:
#   gc.min / gc.max                — spacer GC window (folding + synthesis)
#   avoid: [ self_complementary(>=8) ] — reject hairpin-prone guides

helix "TP53_KO_strict" {
  organism: human(GRCh38)
  cell_line: HEK293T
  profile:   strict

  target: gene(TP53) {
    goal: knockout
    sequence: "ACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGT"
  }

  strategy { modality: crispr_ko; enzyme: SpCas9 }

  constraints {
    guides.count: 3
    gc.min: 0.35
    avoid: [ homopolymer(>=4), self_complementary(>=8) ]
  }

  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel }
  deliver: rnp
  validate: amplicon_seq
}
