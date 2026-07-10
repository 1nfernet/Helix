"""Correctness tests for the prime-editing designer (substitutions, indels, PE3).

The key test reconstructs the edited strand from each pegRNA (both strands) and
asserts it reproduces the intended edit exactly — for substitutions, insertions,
and deletions.
"""

import pytest

from helix.bio import reverse_complement as rc
from helix.compiler.prime_editor import design_prime_edits, parse_edit
from helix.ir.design import OffTargetReport, ResolvedTarget
from helix.ir.enums import Enzyme

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5  # 150 nt
L = len(SEQ)


class _On:
    name = "f"
    version = "0"

    def score(self, s, c):
        return 0.9


class _Off:
    name = "f"
    version = "0"

    def scan(self, s, g):
        return OffTargetReport(max_cfd=0.0, site_count=0, sites=[], scorer="f")


def _target(seq=SEQ):
    return ResolvedTarget(gene="X", genome_build="GRCh38", sequence=seq, length=len(seq), source="t")


def _design(edit):
    return design_prime_edits(_target(), Enzyme.SPCAS9, edit, _On(), _Off())


def _reconstruct(cand, seq, delta):
    """Rebuild the full plus strand as the pegRNA installs it (delta = length change)."""
    rtt_len = len(cand.rtt)
    if cand.strand.value == "+":
        n = cand.nick_position
        return seq[:n] + rc(cand.rtt) + seq[n + rtt_len - delta:]
    n = len(seq) - cand.nick_position
    rcs = rc(seq)
    return rc(rcs[:n] + rc(cand.rtt) + rcs[n + rtt_len - delta:])


def test_parse_edit_forms():
    assert parse_edit("A>G @ 12") == ("A", "G", 11)
    assert parse_edit("->AAC @ 12") == ("-", "AAC", 11)
    assert parse_edit("AC>- @ 12") == ("AC", "-", 11)
    with pytest.raises(ValueError):
        parse_edit("->- @ 1")


def _check_installs(edit, edited):
    delta = len(edited) - L
    pegs = _design(edit)
    assert pegs, f"no pegRNA for {edit}"
    for p in pegs:
        assert _reconstruct(p, SEQ, delta) == edited, f"{p.strand.value} peg wrong for {edit}"
    return pegs


def test_substitution_installs_on_both_strands():
    ref = SEQ[29]
    alt = {"A": "G", "G": "A", "C": "T", "T": "C"}[ref]
    edited = SEQ[:29] + alt + SEQ[30:]
    pegs = _check_installs(f"{ref}>{alt} @ 30", edited)
    assert {p.strand.value for p in pegs} == {"+", "-"}


def test_insertion_installs():
    edited = SEQ[:29] + "AAC" + SEQ[29:]
    _check_installs("->AAC @ 30", edited)


def test_deletion_installs():
    ref = SEQ[29:31]  # 2 nt to delete
    edited = SEQ[:29] + SEQ[31:]
    _check_installs(f"{ref}>- @ 30", edited)


def test_reconstruction_holds_across_positions_and_edit_types():
    checked = 0
    for pos1 in range(25, 120):
        ref1 = SEQ[pos1 - 1]
        alt1 = {"A": "G", "G": "A", "C": "T", "T": "C"}[ref1]
        cases = [
            (f"{ref1}>{alt1} @ {pos1}", SEQ[:pos1 - 1] + alt1 + SEQ[pos1:]),
            (f"->{'GA'} @ {pos1}", SEQ[:pos1 - 1] + "GA" + SEQ[pos1 - 1:]),
            (f"{SEQ[pos1 - 1]}>- @ {pos1}", SEQ[:pos1 - 1] + SEQ[pos1:]),
        ]
        for edit, edited in cases:
            delta = len(edited) - L
            for p in _design(edit):
                assert _reconstruct(p, SEQ, delta) == edited
                checked += 1
    assert checked > 40


def test_pe3_second_nick_attached_within_window():
    pegs = _design("G>A @ 26")  # SEQ[25] == 'G'
    with_pe3 = [p for p in pegs if p.pe3_nick_spacer is not None]
    assert with_pe3, "expected at least one pegRNA with a PE3 nick"
    for p in with_pe3:
        assert 40 <= abs(p.pe3_nick_position - 25) <= 90


def test_homology_arm_enforced():
    edit = "G>A @ 26"
    assert design_prime_edits(_target(), Enzyme.SPCAS9, edit, _On(), _Off(), rtt_len=4) == []


def test_rejects_wrong_ref():
    wrong = "A" if SEQ[25] != "A" else "C"
    with pytest.raises(ValueError):
        design_prime_edits(_target(), Enzyme.SPCAS9, f"{wrong}>G @ 26", _On(), _Off())
