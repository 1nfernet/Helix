"""Tests for broadened biology: enzymes, base editing, prime editing."""

import pytest

from helix.bio import iter_pam_sites, matches_iupac
from helix.compiler.base_editor import design_base_edits
from helix.compiler.pipeline import compile_spec
from helix.compiler.prime_editor import design_prime_edits, parse_edit
from helix.frontend.helix_lang import parse_helix
from helix.frontend.loader import parse_spec
from helix.ir.design import OffTargetReport, ResolvedTarget
from helix.ir.enums import BaseEditor, Enzyme


# --- fakes --------------------------------------------------------------


class _FakeOn:
    name = "fake"
    version = "0"

    def score(self, spacer, context):
        return 0.9


class _FakeOff:
    name = "fake"
    version = "0"

    def scan(self, spacer, genome_build):
        return OffTargetReport(max_cfd=0.0, site_count=0, sites=[], scorer="fake")


def _target(seq):
    return ResolvedTarget(gene="X", genome_build="GRCh38", sequence=seq, length=len(seq), source="test")


# --- enzymes / IUPAC ----------------------------------------------------


def test_iupac_matching():
    assert matches_iupac("AAGAAT", "NNGRRT") and not matches_iupac("AAGCAT", "NNGRRT")
    assert matches_iupac("TTTA", "TTTV") and not matches_iupac("TTTT", "TTTV")


def test_sacas9_and_cas12a_enumeration():
    sa = list(iter_pam_sites("C" * 21 + "AAGAAT" + "TTTT", "NNGRRT", 21, True))
    assert sa and sa[0][2] == "AAGAAT"
    c12 = list(iter_pam_sites("GGGG" + "TTTA" + "A" * 23 + "GG", "TTTV", 23, False))
    assert c12 and c12[0][2] == "TTTA" and c12[0][0] == 8  # spacer starts after 5' PAM


# --- base editing -------------------------------------------------------


def test_cbe_window_conversion_and_bystanders():
    # One plus-strand guide: spacer with C at window positions 4 and 6.
    spacer = "AAACACAAAAAAAAAAAAAA"  # window (pos 4-8) = idx 3..7 = "CACAA"
    seq = spacer + "AGG" + "T" * 20
    guides = design_base_edits(_target(seq), Enzyme.SPCAS9, BaseEditor.CBE, _FakeOn(), _FakeOff())
    g = next(x for x in guides if x.spacer == spacer)
    assert g.base_edit.window == "CACAA"
    assert g.base_edit.edited_product == "TATAA"  # C->T
    assert g.base_edit.edited_positions == [4, 6]
    assert g.base_edit.bystander_count == 1
    assert g.repair is None


def test_abe_targets_adenine():
    spacer = "AAAGAGAAAAAAAAAAAAAA"  # window idx3..7 = "GAGAA" -> A at pos 5,7
    seq = spacer + "TGG" + "T" * 20
    guides = design_base_edits(_target(seq), Enzyme.SPCAS9, BaseEditor.ABE, _FakeOn(), _FakeOff())
    g = next(x for x in guides if x.spacer == spacer)
    assert g.base_edit.target_base == "A" and g.base_edit.product_base == "G"
    # window "GAGAA": A at positions 5, 7, 8 -> all convert to G
    assert g.base_edit.edited_product == "GGGGG"
    assert g.base_edit.edited_positions == [5, 7, 8]


def test_base_edit_via_pipeline():
    seq = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4
    spec = parse_spec({"name": "be", "target": {"gene": "X", "sequence": seq},
                       "strategy": {"modality": "base_edit", "editor": "CBE"},
                       "constraints": {"on_target_min_efficiency": 0.0},
                       "simulate": {"on_target": "heuristic_gc"}})
    design = compile_spec(spec)
    assert design.modality == "base_edit"
    assert all(g.base_edit is not None for g in design.guides)


def test_base_edit_requires_editor():
    spec = parse_spec({"name": "be", "target": {"gene": "X", "sequence": "ACGT" * 30},
                       "strategy": {"modality": "base_edit"}})
    with pytest.raises(ValueError):
        compile_spec(spec)


# --- relaxed-PAM enzymes + CGBE -----------------------------------------


def test_relaxed_pams_expand_targetable_space():
    from helix.compiler.guide_designer import design_guides

    class _Rep:
        def predict(self, seq, cut):
            from helix.ir.design import RepairOutcome
            return RepairOutcome(frameshift_fraction=0.5, top_outcomes=[], predictor="fake")

    seq = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5
    t = _target(seq)
    n_spcas9 = len(design_guides(t, Enzyme.SPCAS9, _FakeOn(), _FakeOff(), _Rep()))
    n_spg = len(design_guides(t, Enzyme.SPG, _FakeOn(), _FakeOff(), _Rep()))
    n_spry = len(design_guides(t, Enzyme.SPRY, _FakeOn(), _FakeOff(), _Rep()))
    assert n_spg > n_spcas9 and n_spry > n_spg  # NGN > NGG, NRN broadest


def test_cgbe_converts_c_to_g():
    seq = "AAACACAAAAAAAAAAAAAA" + "AGG" + "T" * 20  # window (pos 4-8) = "CACAA"
    guides = design_base_edits(_target(seq), Enzyme.SPCAS9, BaseEditor.CGBE, _FakeOn(), _FakeOff())
    g = next(x for x in guides if x.spacer.startswith("AAACAC"))
    assert g.base_edit.target_base == "C" and g.base_edit.product_base == "G"
    assert g.base_edit.edited_product == "GAGAA"  # C->G at positions 4 and 6


def test_base_edit_target_position_filters_by_window():
    # Targeting a base returns only guides whose editing window covers it
    # (the mechanism behind clicking a C/A in the 3D helix).
    seq = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4
    t = _target(seq)
    allg = design_base_edits(t, Enzyme.SPCAS9, BaseEditor.CBE, _FakeOn(), _FakeOff())
    assert allg
    pos = allg[0].base_edit.window_abs_start + 2  # a base inside the first guide's window
    targeted = design_base_edits(
        t, Enzyme.SPCAS9, BaseEditor.CBE, _FakeOn(), _FakeOff(), target_pos=pos
    )
    assert targeted, "the picked guide survives"
    assert all(g.base_edit.window_abs_start <= pos < g.base_edit.window_abs_start + 5 for g in targeted)
    assert len(targeted) < len(allg), "the filter narrows the set"


def test_base_edit_pipeline_targets_picked_base():
    seq = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4
    base = {"name": "be", "target": {"gene": "X", "sequence": seq},
            "strategy": {"modality": "base_edit", "editor": "CBE"},
            "constraints": {"on_target_min_efficiency": 0.0},
            "simulate": {"on_target": "heuristic_gc"}}
    all_design = compile_spec(parse_spec(base))
    p0 = all_design.guides[0].base_edit.window_abs_start + 2  # 0-based
    base["target"] = {"gene": "X", "sequence": seq, "edit": f"C>T @ {p0 + 1}"}  # DSL is 1-based
    d = compile_spec(parse_spec(base))
    assert d.guides and len(d.guides) < len(all_design.guides)
    assert all(g.base_edit.window_abs_start <= p0 < g.base_edit.window_abs_start + 5 for g in d.guides)


# --- prime editing ------------------------------------------------------


def test_parse_edit():
    assert parse_edit("A>G @ 12") == ("A", "G", 11)
    with pytest.raises(ValueError):
        parse_edit("nonsense")


def test_prime_edit_rejects_wrong_ref():
    seq = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4
    with pytest.raises(ValueError):
        design_prime_edits(_target(seq), Enzyme.SPCAS9, "A>T @ 26", _FakeOn(), _FakeOff())  # pos26 is G


def test_prime_edit_via_pipeline_requires_edit():
    spec = parse_spec({"name": "pe", "target": {"gene": "X", "sequence": "ACGT" * 30},
                       "strategy": {"modality": "prime_edit"}})
    with pytest.raises(ValueError):
        compile_spec(spec)


# --- grammar accepts the new fields -------------------------------------


def test_grammar_base_edit_spec():
    spec = parse_helix(
        'helix "b" { target: gene(TP53) { sequence: "ACGTACGTACGTACGTACGTACGTGG" }'
        '  strategy { modality: base_edit; editor: CBE } }'
    )
    assert spec.strategy.modality.value == "base_edit"
    assert spec.strategy.editor.value == "CBE"
