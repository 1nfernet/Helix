"""Tests for the CRISPResso2 analysis loop (offline).

Pure parsers are tested against the tool's documented output format; the
subprocess backend is exercised via an injected executor; reconciliation is
tested for both agreement and divergence.
"""

import os

import pytest

from helix.analysis.crispresso import (
    Crispresso2Backend,
    Crispresso2NotConfigured,
    CrispressoAnalyzer,
    RawCrispresso,
    parse_frameshift_analysis,
    parse_quantification,
)
from helix.analysis.reconcile import reconcile
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec

_QUANT = (
    "Amplicon\tUnmodified%\tModified%\tReads_in_input\tReads_aligned_all_amplicons\t"
    "Reads_aligned\tUnmodified\tModified\tDiscarded\tInsertions\tDeletions\tSubstitutions\n"
    "Reference\t57.5\t42.5\t12000\t10000\t10000\t5750\t4250\t0\t900\t3200\t150\n"
)
_FRAMESHIFT = (
    "Frameshift analysis:\n"
    "\tNoncoding mutation:100 reads\n"
    "\tIn-frame mutation:1250 reads\n"
    "\tFrameshift mutation:2900 reads\n"
)


def test_parse_quantification():
    q = parse_quantification(_QUANT)
    assert q["editing_efficiency"] == pytest.approx(0.425)
    assert q["reads_aligned"] == 10000
    assert q["modified_reads"] == 4250
    assert q["deletions"] == 3200


def test_parse_frameshift():
    f = parse_frameshift_analysis(_FRAMESHIFT)
    assert f["frameshift"] == 2900 and f["in_frame"] == 1250
    assert f["frameshift_fraction"] == pytest.approx(2900 / 4150)


class _FakeBackend:
    def run(self, amplicon, reads, coding_seq):
        return RawCrispresso(quantification=_QUANT, frameshift=_FRAMESHIFT if coding_seq else None)


def test_analyzer_builds_editing_analysis():
    a = CrispressoAnalyzer(_FakeBackend()).analyze("ACGT", "reads.fq", coding_seq="ACGT")
    assert a.editing_efficiency == pytest.approx(0.425)
    assert a.frameshift_fraction == pytest.approx(2900 / 4150)
    assert a.analyzer == "crispresso2"


def test_analyzer_without_coding_has_no_frameshift():
    a = CrispressoAnalyzer(_FakeBackend()).analyze("ACGT", "reads.fq", coding_seq=None)
    assert a.frameshift_fraction is None


def test_backend_reads_files_via_injected_executor():
    def fake_exec(binary, args, out_base):
        with open(os.path.join(out_base, "CRISPResso_quantification_of_editing_frequency.txt"), "w") as fh:
            fh.write(_QUANT)
        with open(os.path.join(out_base, "ref.Frameshift_analysis.txt"), "w") as fh:
            fh.write(_FRAMESHIFT)

    raw = Crispresso2Backend(execute=fake_exec).run("ACGT", "reads.fq", coding_seq="ACGT")
    assert "Modified%" in raw.quantification
    assert raw.frameshift is not None


def test_backend_not_configured():
    backend = Crispresso2Backend(binary="definitely-not-a-real-binary-xyz")
    with pytest.raises(Crispresso2NotConfigured):
        backend.run("ACGT", "reads.fq")


def _design():
    spec = parse_spec(
        {"name": "loop", "target": {"gene": "TP53",
                                    "sequence": "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4}}
    )
    return compile_spec(spec)


def test_reconcile_agrees_when_observed_matches_prediction():
    design = _design()
    predicted = design.selected[0].repair.frameshift_fraction
    analysis = CrispressoAnalyzer(_FakeBackend()).analyze("A", "r")  # no coding -> None
    analysis = analysis.model_copy(update={"frameshift_fraction": predicted})
    result = reconcile(design, analysis, tolerance=0.15)
    assert result.frameshift_agrees is True
    assert result.frameshift_delta == 0.0


def test_reconcile_diverges_when_observed_far():
    design = _design()
    predicted = design.selected[0].repair.frameshift_fraction
    analysis = CrispressoAnalyzer(_FakeBackend()).analyze("A", "r")
    analysis = analysis.model_copy(update={"frameshift_fraction": max(0.0, predicted - 0.6)})
    result = reconcile(design, analysis, tolerance=0.15)
    assert result.frameshift_agrees is False


def test_reconcile_handles_missing_frameshift():
    design = _design()
    analysis = CrispressoAnalyzer(_FakeBackend()).analyze("A", "r")  # frameshift None
    result = reconcile(design, analysis)
    assert result.frameshift_agrees is None
    assert any("No coding frameshift" in n for n in result.notes)
