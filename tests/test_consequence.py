"""Tests for the codon / protein-consequence layer and silent PAM-blocking."""

from helix.codons import classify_change, classify_changes, codon_span, translate_codon
from helix.compiler.consequence import base_edit_consequence, edit_consequence
from helix.compiler.hdr_designer import _choose_pam_block
from helix.compiler.pipeline import compile_spec
from helix.frontend.helix_lang import parse_helix
from helix.ir.enums import Strand


# ---- genetic code / frame ----

def test_genetic_code_spot_checks():
    assert translate_codon("ATG") == "M"
    assert translate_codon("TGG") == "W"
    assert translate_codon("TAA") == translate_codon("TAG") == translate_codon("TGA") == "*"
    assert translate_codon("NNN") == "X"


def test_codon_span_respects_frame():
    assert codon_span(0, 1) is None       # before the first whole codon
    assert codon_span(1, 1) == (1, 0, 0)  # first codon starts at 1
    assert codon_span(6, 0) == (6, 2, 0)


def test_classify_synonymous_missense_nonsense():
    assert classify_change("CTG", 0, 2, "A")["kind"] == "synonymous"   # CTG->CTA both Leu
    assert classify_change("GAA", 0, 1, "T")["kind"] == "missense"     # GAA(E)->GTA(V)
    stop = classify_change("AAACAGGGT", 0, 3, "T")                     # CAG(Q)->TAG(*)
    assert stop["kind"] == "nonsense" and stop["alt_aa"] == "*"
    assert classify_change("TAAGGG", 0, 0, "C")["kind"] == "stop-loss"  # TAA(*)->CAA(Q)


def test_classify_returns_none_off_window_or_ambiguous():
    assert classify_change("ATG", 0, 0, "N") is None       # non-ACGT alt
    assert classify_change("AT", 0, 0, "C") is None        # codon runs off the window
    assert classify_change("ANG", 0, 0, "C") is None       # ref codon has N


# ---- edit-level consequences ----

def test_edit_consequence_substitution_and_none_without_frame():
    c = edit_consequence("AAACAGGGT", 0, 3, "C", "T")  # CAG->TAG
    assert c.kind == "nonsense" and "STOP" in c.label
    assert edit_consequence("AAACAGGGT", None, 3, "C", "T") is None


def test_edit_consequence_indels():
    assert edit_consequence("ACGACG", 0, 3, "-", "A").kind == "frameshift"     # +1 nt
    assert edit_consequence("ACGACG", 0, 3, "AC", "-").kind == "frameshift"    # -2 nt
    assert edit_consequence("ACGACG", 0, 3, "-", "ACG").kind == "in-frame-indel"  # +3 nt


def test_two_edits_in_one_codon_scored_as_combined_mutant():
    # CCA(Pro): editing both C's -> TTA(Leu). Must be ONE codon call (P>L), not two.
    calls = classify_changes("AAACCAGGG", 0, [(3, "T"), (4, "T")])
    assert len(calls) == 1
    assert calls[0]["ref_aa"] == "P" and calls[0]["alt_aa"] == "L" and calls[0]["kind"] == "missense"


def test_double_edit_stop_codon_is_stop_loss_not_silent():
    # ABE both A's of TAA(stop) -> TGG(Trp) is STOP-LOSS. Classifying each base alone
    # would see STOP->STOP (silent) and hide it; the combined codon must be scored.
    c = base_edit_consequence("TAAGGGCCC", 0, [(1, "G"), (2, "G")])
    assert c.kind == "stop-loss" and c.alt_aa == "W"


def test_base_edit_consequence_reports_worst_and_bystanders():
    # window "CAG...": change pos3 C->T (CAG->TAG stop), plus a synonymous bystander.
    w = "AAACAGCTG"  # AAA(K) CAG(Q) CTG(L)
    c = base_edit_consequence(w, 0, [(3, "T"), (8, "A")])  # CAG->TAG (stop), CTG->CTA (syn)
    assert c.kind == "nonsense"
    assert "1 of 2" in c.note
    assert base_edit_consequence(w, None, [(3, "T")]) is None


# ---- silent PAM-block guarantee ----

def test_choose_pam_block_prefers_synonymous():
    seq = "CTG" * 20  # all Leu, frame 0 -> a 3rd-position change is synonymous
    idx, base, silent = _choose_pam_block(seq, Strand.PLUS, (3, 6), True, True,
                                          pos0=5, ref_len=1, arm=50, length=len(seq), frame=0)
    assert silent is True
    assert classify_change(seq, 0, idx, base)["kind"] == "synonymous"


def test_choose_pam_block_flags_when_no_synonymous_option():
    seq = "TGG" * 20  # all Trp (unique codon) -> no synonymous break exists
    idx, base, silent = _choose_pam_block(seq, Strand.PLUS, (0, 3), True, True,
                                          pos0=1, ref_len=1, arm=50, length=len(seq), frame=0)
    assert silent is False
    assert classify_change(seq, 0, idx, base)["kind"] != "synonymous"


def test_choose_pam_block_unknown_without_frame():
    seq = "CTG" * 20
    _, _, silent = _choose_pam_block(seq, Strand.PLUS, (3, 6), True, True,
                                     pos0=5, ref_len=1, arm=50, length=len(seq), frame=None)
    assert silent is None


# ---- pipeline integration ----

_SEQ = ("ATGGCCAAGCTGACCGAGCTGCAGGACAAGCTGACCGAGTGGAAGCTGACCGAGCTGCAGGAC"
        "AAGCTGACCGAGCTGCAGGACAAGCTGACCGAGTGGAAGCTGACCGAGCTG")


def _compile(frame_line, mod, extra, edit=""):
    e = f'edit: "{edit}";' if edit else ""
    return compile_spec(parse_helix(
        f'helix "v" {{ organism: human(GRCh38) '
        f'  target: gene(TP53) {{ goal: knockout; {frame_line} {e} sequence: "{_SEQ}" }} '
        f'  strategy {{ modality: {mod}{extra} }} constraints {{ guides.count: 5 }} '
        f'  simulate {{ sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel }} }}'))


def test_pipeline_base_edit_consequences_gated_on_frame():
    with_frame = _compile("frame: 0;", "base_edit", "; enzyme: SpCas9; editor: CBE")
    assert any(g.base_edit and g.base_edit.consequence for g in with_frame.guides)
    no_frame = _compile("", "base_edit", "; enzyme: SpCas9; editor: CBE")
    assert all(g.base_edit and g.base_edit.consequence is None for g in no_frame.guides)


def test_pipeline_hdr_silent_pam_block_is_genuinely_synonymous():
    d = _compile("frame: 0;", "hdr", "; enzyme: SpCas9; donor: ssodn", edit=f"{_SEQ[74]}>A @ 75")
    silent = [g.hdr for g in d.guides if g.hdr and g.hdr.silent_pam_block is True]
    assert silent, "expected at least one guide with a guaranteed-synonymous PAM-block"
    # and a run without a frame leaves the flag unknown (None)
    d2 = _compile("", "hdr", "; enzyme: SpCas9; donor: ssodn", edit=f"{_SEQ[74]}>A @ 75")
    assert all(g.hdr.silent_pam_block is None for g in d2.guides if g.hdr)
