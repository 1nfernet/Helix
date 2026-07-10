"""Unit tests for the sequence-biology primitives."""

from helix.bio import (
    contains_restriction_site,
    gc_content,
    iter_ngg_sites,
    max_homopolymer_run,
    reverse_complement,
)


def test_reverse_complement():
    assert reverse_complement("ATGC") == "GCAT"
    assert reverse_complement("aacc") == "GGTT"


def test_gc_content():
    assert gc_content("GGCC") == 1.0
    assert gc_content("ATAT") == 0.0
    assert gc_content("") == 0.0


def test_max_homopolymer_run():
    assert max_homopolymer_run("AAATC") == 3
    assert max_homopolymer_run("ATATAT") == 1
    assert max_homopolymer_run("") == 0


def test_restriction_site_detects_both_strands():
    # BsaI site GGTCTC and its reverse complement GAGACC.
    assert contains_restriction_site("AAAGGTCTCAAA", "BsaI")
    assert contains_restriction_site("AAAGAGACCAAA", "BsaI")
    assert not contains_restriction_site("AAAAAAAA", "BsaI")


def test_iter_ngg_sites_finds_expected_spacer():
    # 20 A's, then NGG at index 20 (A GG). Spacer should be the 20 A's.
    seq = "A" * 20 + "AGG" + "TTTT"
    sites = list(iter_ngg_sites(seq, spacer_len=20))
    assert sites, "expected at least one NGG site"
    start, spacer, pam = sites[0]
    assert start == 0
    assert spacer == "A" * 20
    assert pam.endswith("GG")
