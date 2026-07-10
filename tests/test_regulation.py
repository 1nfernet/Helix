"""Tests for the CRISPRi / CRISPRa (dCas9 regulation) designer."""

from helix.compiler.pipeline import compile_spec
from helix.frontend.helix_lang import parse_helix
from helix.frontend.loader import parse_spec

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5  # 150 nt


def _spec(modality, tss, **over):
    data = {
        "name": modality, "cell_line": "HEK293T",
        "target": {"gene": "TP53", "sequence": SEQ, "tss": tss},
        "strategy": {"modality": modality},
        "constraints": {"on_target_min_efficiency": 0.0, "off_target_max_cfd": 0.3,
                        "guides_count": 3, "max_homopolymer": 5},
        "simulate": {"on_target": "heuristic_gc", "off_target": "mock_seed"},
    }
    data.update(over)
    return parse_spec(data)


def test_crispri_forces_dcas9_and_places_downstream():
    d = compile_spec(_spec("crispri", tss=40))
    assert d.modality == "crispri"
    assert d.resolved_enzyme.value == "dCas9"  # always dCas9, no cut
    top = d.selected[0]
    assert top.regulation is not None
    assert top.regulation.mode == "crispri" and top.regulation.optimal
    # CRISPRi window is -50..+300; the best guide sits downstream of the TSS
    assert -50 <= top.regulation.tss_offset <= 300
    assert top.repair is None


def test_crispra_places_upstream():
    d = compile_spec(_spec("crispra", tss=130))
    top = d.selected[0]
    assert top.regulation.mode == "crispra" and top.regulation.optimal
    assert -400 <= top.regulation.tss_offset <= -50  # upstream promoter


def test_crispri_cargo_includes_repressor():
    d = compile_spec(_spec("crispri", tss=60))
    # dCas9 (4.1) + KRAB (0.5)
    assert abs(d.delivery.cargo_kb - 4.6) < 0.01


def test_grammar_parses_crispri_tss():
    spec = parse_helix(
        'helix "i" { organism: human(GRCh38) '
        '  target: gene(TP53) { sequence: "' + SEQ + '"; tss: 40 } '
        '  strategy { modality: crispri } }'
    )
    assert spec.strategy.modality.value == "crispri"
    assert spec.target.tss == 40
