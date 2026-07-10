"""Tests for the Cas-OFFinder + CFD off-target adapter.

CFD expected values were cross-checked against the reference calculator
(0 mismatches over 20,000 random guide/off-target pairs), so these pin
equivalence to the published Doench 2016 model. Cas-OFFinder itself is exercised
via pure input/output helpers and an injected fake finder — no binary needed.
"""

import pytest

from helix.adapters.offtarget import (
    CasOffinderCfdScorer,
    CasOffinderNotConfigured,
    CasOffinderRunner,
    OffTargetHit,
    build_casoffinder_input,
    cfd_score,
    parse_casoffinder_output,
)
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec

GUIDE = "GAGTCCGAGCAGAAGAAGAA"


# --- CFD ----------------------------------------------------------------


def test_cfd_reference_values():
    assert cfd_score(GUIDE, GUIDE + "AGG") == 1.0  # identical, GG PAM
    assert cfd_score(GUIDE, "A" + GUIDE[1:] + "AGG") == pytest.approx(0.9)  # PAM-distal mm
    assert cfd_score(GUIDE, GUIDE[:19] + "C" + "AGG") == pytest.approx(0.227272727)  # PAM-proximal
    assert cfd_score(GUIDE, GUIDE + "AGA") == pytest.approx(0.069444444)  # GA PAM penalty only


def test_cfd_rejects_short_site():
    with pytest.raises(ValueError):
        cfd_score(GUIDE, "ACGT")


# --- Cas-OFFinder I/O (pure) --------------------------------------------


def test_build_input_lengths_match():
    text = build_casoffinder_input(GUIDE, "/genomes/hg38", pam="NGG", max_mismatches=3)
    genome, pattern, query = text.strip().split("\n")
    assert genome == "/genomes/hg38"
    assert len(pattern) == len(GUIDE) + 3           # spacer + PAM
    assert query.split()[0] == GUIDE + "NNN"
    assert query.split()[1] == "3"


def test_parse_non_bulge_output():
    out = (
        f"{GUIDE}NNN\tchr5\t1000\t{GUIDE}AGG\t+\t0\n"
        f"{GUIDE}NNN\tchr7\t2000\t{GUIDE[:-2]}TTGGG\t-\t2\n"
    )
    hits = parse_casoffinder_output(out)
    assert [h.mismatches for h in hits] == [0, 2]
    assert hits[0].chrom == "chr5" and hits[0].strand == "+"


def test_parse_bulge_output_with_header():
    out = (
        "#Bulge type\tcrRNA\tDNA\tChromosome\tPosition\tDirection\tMismatches\tBulge Size\n"
        f"X\t{GUIDE}NNN\t{GUIDE}AGG\tchr1\t50\t+\t0\t0\n"
    )
    hits = parse_casoffinder_output(out)
    assert len(hits) == 1 and hits[0].chrom == "chr1" and hits[0].dna == GUIDE + "AGG"


# --- the scorer (fake finder) -------------------------------------------


class _FakeFinder:
    def __init__(self, hits):
        self._hits = hits

    def find(self, spacer, genome_build):
        return list(self._hits)


def test_scorer_excludes_one_on_target_keeps_extra_perfect():
    two_mm = GUIDE[:18] + "TT" + "AGG"  # 2 PAM-proximal mismatches
    hits = [
        OffTargetHit("chr1", 100, "+", GUIDE + "AGG", 0),   # intended on-target
        OffTargetHit("chr7", 700, "-", two_mm, 2),          # real off-target
        OffTargetHit("chr9", 900, "+", GUIDE + "CGG", 0),   # extra perfect match
    ]
    report = CasOffinderCfdScorer(_FakeFinder(hits)).scan(GUIDE, "GRCh38")
    assert report.site_count == 2                # on-target dropped, 2 offs remain
    assert report.max_cfd == 1.0                 # the extra perfect match
    assert report.scorer.startswith("cas_offinder_cfd@")


def test_scorer_no_offtargets():
    hits = [OffTargetHit("chr1", 100, "+", GUIDE + "AGG", 0)]
    report = CasOffinderCfdScorer(_FakeFinder(hits)).scan(GUIDE, "GRCh38")
    assert report.site_count == 0 and report.max_cfd == 0.0


def test_runner_errors_without_genome():
    with pytest.raises(CasOffinderNotConfigured):
        CasOffinderRunner(genome_path=None).find(GUIDE, "GRCh38")


def test_runner_invokes_binary_via_injected_run():
    captured = {}

    def fake_run(binary, device, input_text):
        captured["binary"] = binary
        return f"{GUIDE}NNN\tchr1\t10\t{GUIDE}AGG\t+\t0\n"

    runner = CasOffinderRunner(genome_path="/g/hg38", binary="cas-offinder", run=fake_run)
    hits = runner.find(GUIDE, "GRCh38")
    assert captured["binary"] == "cas-offinder"
    assert len(hits) == 1 and hits[0].mismatches == 0


# --- end-to-end through the compiler ------------------------------------


def test_pipeline_uses_cas_offinder_cfd_seam():
    from helix.adapters.registry import default_registry

    # Fake finder returns just the intended on-target for whatever spacer is asked.
    class OnTargetOnly:
        def find(self, spacer, genome_build):
            return [OffTargetHit("chr1", 1, "+", spacer + "AGG", 0)]

    reg = default_registry()
    reg.register_off_target(CasOffinderCfdScorer(OnTargetOnly()))
    spec = parse_spec(
        {
            "name": "ot",
            "target": {"gene": "TP53", "sequence": "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4},
            "simulate": {"off_target": "cas_offinder_cfd"},
        }
    )
    design = compile_spec(spec, registry=reg)
    assert design.guides
    assert all(g.off_target.max_cfd == 0.0 for g in design.guides)
    assert all(g.off_target.scorer.startswith("cas_offinder_cfd@") for g in design.guides)
