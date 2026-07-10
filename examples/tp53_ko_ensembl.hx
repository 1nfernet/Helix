# Helix grammar — knock out TP53, resolving the target sequence from Ensembl.
#
# No inline sequence: the `ensembl` provider looks up the gene by symbol against
# GRCh38 and fetches a bounded edit window. Requires network access.

helix "TP53_KO_HEK293_ensembl" {
  organism: human(GRCh38)
  cell_line: HEK293T

  target: gene(TP53) {
    goal: knockout
    region: exon(2..4)     # human-readable hint; exon-precise windows are Phase 3
  }

  strategy {
    modality: crispr_ko
    enzyme: auto
  }

  constraints {
    on_target.min_efficiency: 0.5    # Doench 2014 scores are absolute, not percentiles
    off_target.max_cfd: 0.3
    guides.count: 1                  # real exon-2 guides are demanding; the mock
                                     # off-target scorer also filters some (use
                                     # cas_offinder_cfd with a genome in practice)
    avoid: [ homopolymer(>=4), restriction_site(BsaI) ]
  }

  simulate {
    sequence_provider: ensembl       # first real adapter: fetches the window
    on_target: rule_set_1            # Doench 2014, real on-target model
    off_target: mock_seed
    repair_outcome: mock_indel
  }

  deliver: rnp
  validate: amplicon_seq
}
