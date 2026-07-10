"""Tests for variant-aware guide design (seed/PAM SNP flagging)."""

from helix.adapters.registry import default_registry
from helix.adapters.variants import EnsemblVariantProvider, StaticVariantProvider
from helix.compiler.pipeline import compile_spec
from helix.compiler.variants import annotate_variants
from helix.ir.design import GuideCandidate, OffTargetReport, ResolvedTarget, SeqVariant, TargetLocus
from helix.ir.enums import Enzyme, Strand
from helix.frontend.helix_lang import parse_helix

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5


def _guide(window_offset=10, strand=Strand.PLUS):
    return GuideCandidate(
        spacer="A" * 20, pam="AGG", strand=strand, window_offset=window_offset, cut_site=window_offset + 17,
        gc_content=0.5, on_target_score=0.7,
        off_target=OffTargetReport(max_cfd=0.0, site_count=0, sites=[], scorer="fake"),
    )


def test_annotate_classifies_seed_pam_protospacer():
    g = _guide(window_offset=10)  # plus strand SpCas9: proto [10,30), seed [20,30), PAM [30,33)
    variants = [
        SeqVariant(id="pam", window_pos=31, frequency=0.1),
        SeqVariant(id="seed", window_pos=25, frequency=0.1),
        SeqVariant(id="proto", window_pos=12, frequency=0.1),
        SeqVariant(id="outside", window_pos=5, frequency=0.1),
    ]
    annotate_variants([g], variants, Enzyme.SPCAS9)
    by_id = {h.id: h.region for h in g.variant_hits}
    assert by_id == {"pam": "PAM", "seed": "seed", "proto": "protospacer"}  # 'outside' dropped


def test_ensembl_provider_maps_genomic_to_window_both_strands():
    def fake_get_json(url):
        return [
            {"id": "rsA", "start": 1010, "alleles": ["C", "T"], "minor_allele_frequency": 0.2},
            {"id": "rsFar", "start": 99999},  # outside the window -> dropped
        ]

    plus = ResolvedTarget(gene="X", genome_build="GRCh38", sequence="A" * 100, length=100, source="t",
                          locus=TargetLocus(chromosome="17", start=1000, end=1099, strand=1))
    minus = plus.model_copy(update={"locus": TargetLocus(chromosome="17", start=1000, end=1099, strand=-1)})
    p = EnsemblVariantProvider(get_json=fake_get_json, host="http://x")
    vp = p.variants(plus)
    vm = p.variants(minus)
    assert len(vp) == 1 and vp[0].window_pos == 10 and vp[0].frequency == 0.2  # 1010-1000
    assert vm[0].window_pos == 89  # 1099-1010


def test_ensembl_provider_no_locus_returns_empty():
    t = ResolvedTarget(gene="X", genome_build="GRCh38", sequence="A" * 100, length=100, source="t")
    assert EnsemblVariantProvider(get_json=lambda u: [], host="http://x").variants(t) == []


def test_common_variant_constraint_rejects_guide():
    d0 = compile_spec(parse_helix(
        'helix "v" { organism: human(GRCh38) '
        f'  target: gene(TP53) {{ goal: knockout; sequence: "{SEQ}" }} '
        '  strategy { modality: crispr_ko; enzyme: SpCas9 } constraints { guides.count: 1 } '
        '  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel } }'))
    g = next(g for g in d0.guides if g.strand is Strand.PLUS)
    seed_pos = g.window_offset + 15

    reg = default_registry()
    reg.register_variant(StaticVariantProvider([SeqVariant(id="rs1", window_pos=seed_pos, frequency=0.05)]))
    d = compile_spec(parse_helix(
        'helix "v" { organism: human(GRCh38) '
        f'  target: gene(TP53) {{ goal: knockout; sequence: "{SEQ}" }} '
        '  strategy { modality: crispr_ko; enzyme: SpCas9 } '
        '  constraints { guides.count: 1; avoid: [ common_variant(>=0.01) ] } '
        '  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel; variant_source: static } }'),
        registry=reg)
    flagged = next(g for g in d.guides if g.variant_hits)
    check = next(c for c in flagged.checks if c.name == "common_variant")
    assert not check.passed and flagged.variant_hits[0].region == "seed"
