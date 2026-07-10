"""Tests for the dual-cut deletion designer."""

import pytest

from helix.compiler.pipeline import compile_spec
from helix.frontend.helix_lang import parse_helix
from helix.frontend.loader import parse_spec

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5  # 150 nt


def _spec(delete="40..95", **over):
    data = {
        "name": "del", "cell_line": "HEK293T",
        "target": {"gene": "TP53", "sequence": SEQ, "delete": delete},
        "strategy": {"modality": "deletion", "enzyme": "SpCas9"},
        "constraints": {"on_target_min_efficiency": 0.0, "off_target_max_cfd": 0.3,
                        "guides_count": 2, "max_homopolymer": 5},
        "simulate": {"on_target": "heuristic_gc", "off_target": "mock_seed"},
    }
    data.update(over)
    return parse_spec(data)


def test_deletion_brackets_the_span():
    d = compile_spec(_spec("40..95"))
    assert d.modality == "deletion" and d.feasible
    p = d.deletion
    assert p is not None
    # two flanking cuts, ordered, near the requested boundaries
    assert p.left_cut < p.right_cut
    assert p.deletion_size == p.right_cut - p.left_cut
    assert abs(p.left_cut - 39) <= 30 and abs(p.right_cut - 95) <= 30
    assert " / " in p.junction
    assert len(d.selected) == 2


def test_deletion_requires_span():
    with pytest.raises(ValueError):
        compile_spec(_spec(target={"gene": "TP53", "sequence": SEQ}))


def test_deletion_infeasible_when_no_flanking_guide():
    # A boundary at the very edge has no PAM-flanked cut within range.
    d = compile_spec(_spec("1..3"))
    assert not d.feasible
    assert d.deletion is None and d.infeasibility_notes


def test_grammar_parses_delete():
    spec = parse_helix(
        'helix "d" { organism: human(GRCh38) '
        '  target: gene(TP53) { sequence: "' + SEQ + '"; delete: "40..95" } '
        '  strategy { modality: deletion; enzyme: SpCas9 } }'
    )
    assert spec.strategy.modality.value == "deletion"
    assert spec.target.delete == "40..95"
