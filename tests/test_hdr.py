"""Tests for the HDR knock-in designer."""

import pytest

from helix.compiler.pipeline import compile_spec
from helix.frontend.helix_lang import parse_helix
from helix.frontend.loader import parse_spec

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5  # 150 nt


def _spec(edit="C>T @ 50", donor="ssodn", **over):
    data = {
        "name": "ki", "cell_line": "HEK293T",
        "target": {"gene": "TP53", "sequence": SEQ, "edit": edit},
        "strategy": {"modality": "hdr", "enzyme": "SpCas9", "donor": donor},
        "constraints": {"on_target_min_efficiency": 0.0, "off_target_max_cfd": 0.3,
                        "guides_count": 1, "max_homopolymer": 5},
        "simulate": {"on_target": "heuristic_gc", "off_target": "mock_seed"},
    }
    data.update(over)
    return parse_spec(data)


def test_hdr_designs_guide_and_donor():
    d = compile_spec(_spec())
    assert d.modality == "hdr" and d.feasible
    g = d.selected[0]
    h = g.hdr
    assert h is not None
    p0 = h.edit_pos
    # a close cut and a reconstructable donor
    assert h.cut_to_edit_distance <= 30
    assert h.sequence == h.left_arm + h.insert + h.right_arm
    assert h.insert == "T"  # C>T installs T
    # arms are the requested length, clamped at the sequence boundaries
    assert len(h.left_arm) == min(h.arm_length, p0)
    assert len(h.right_arm) == min(h.arm_length, len(SEQ) - p0 - 1)
    assert g.repair is None and g.base_edit is None


def test_hdr_arms_are_genomic_except_pam_block():
    d = compile_spec(_spec())
    h = d.selected[0].hdr
    p0 = h.edit_pos
    left_ref = SEQ[max(0, p0 - h.arm_length):p0]
    right_ref = SEQ[p0 + 1:p0 + 1 + h.arm_length]  # ref_len==1 for a substitution
    diffs = sum(a != b for a, b in zip(h.left_arm, left_ref)) + \
        sum(a != b for a, b in zip(h.right_arm, right_ref))
    assert diffs <= 1  # arms match the genome except for at most one PAM-blocking base
    assert h.pam_disrupted is True  # the top guide can block re-cutting


def test_hdr_insertion_tag():
    d = compile_spec(_spec(edit="->GATTACAAG @ 60"))
    h = d.selected[0].hdr
    assert h.insert == "GATTACAAG" and "GATTACAAG" in h.sequence
    assert h.edit.startswith("ins ")


def test_hdr_requires_edit_and_donor():
    with pytest.raises(ValueError):
        compile_spec(_spec(edit=None, target={"gene": "TP53", "sequence": SEQ}))
    with pytest.raises(ValueError):
        compile_spec(_spec(strategy={"modality": "hdr", "enzyme": "SpCas9"}))


def test_grammar_parses_hdr_donor():
    spec = parse_helix(
        'helix "k" { organism: human(GRCh38) '
        '  target: gene(TP53) { sequence: "' + SEQ + '"; edit: "C>T @ 50" } '
        '  strategy { modality: hdr; enzyme: SpCas9; donor: ssodn } }'
    )
    assert spec.strategy.modality.value == "hdr"
    assert spec.strategy.donor.value == "ssodn"
