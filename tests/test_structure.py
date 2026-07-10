"""Tests for structural simulation (offline)."""

import pytest

from helix.ir.design import GuideCandidate, OffTargetReport, ResolvedTarget
from helix.ir.enums import Strand
from helix.structure import (
    StructureAnalyzer,
    SubprocessFoldingBackend,
    build_complex,
    to_af3_json,
    to_rna,
)
from helix.structure.backend import StructureNotConfigured
from helix.structure.data.spcas9 import SGRNA_SCAFFOLD, SPCAS9_PROTEIN

SEQ = "ACGT" * 20  # 80 nt


def _guide(spacer="ACGTACGTACGTACGTACGT", offset=10):
    return GuideCandidate(
        spacer=spacer, pam="AGG", strand=Strand.PLUS, window_offset=offset, cut_site=offset + 17,
        gc_content=0.5, on_target_score=0.6,
        off_target=OffTargetReport(max_cfd=0.0, site_count=0, sites=[], scorer="f"),
        composite_score=0.6,
    )


def _target():
    return ResolvedTarget(gene="TP53", genome_build="GRCh38", sequence=SEQ, length=len(SEQ), source="t")


def test_to_rna():
    assert to_rna("ACGT") == "ACGU"


def test_build_complex_assembles_entities():
    cx = build_complex(_guide(), _target(), flank=10)
    assert cx.protein == SPCAS9_PROTEIN and len(cx.protein) == 1368
    assert cx.guide_rna == to_rna("ACGTACGTACGTACGTACGT" + SGRNA_SCAFFOLD)
    assert cx.target_dna_sense in SEQ  # a real slice around the protospacer
    from helix.bio import reverse_complement
    assert cx.target_dna_antisense == reverse_complement(cx.target_dna_sense)
    assert cx.label == "TP53:ACGTACGTACGTACGTACGT"


def test_af3_json_has_four_entities():
    j = to_af3_json(build_complex(_guide(), _target()))
    kinds = [list(e.keys())[0] for e in j["sequences"]]
    assert kinds == ["protein", "rna", "dna", "dna"]
    assert j["dialect"] == "alphafold3"


class _FakeBackend:
    def __init__(self, iptm):
        self.name = "fake"
        self._iptm = iptm

    def fold(self, complex_json):
        return {"ptm": 0.8, "iptm": self._iptm, "plddt": 85.0, "structure_path": "/tmp/x.cif"}


def test_analyzer_flags_well_formed():
    a = StructureAnalyzer(_FakeBackend(iptm=0.8)).assess(_guide(), _target())
    assert a.well_formed and a.confidence.iptm == 0.8 and a.backend == "fake"
    assert a.structure_path == "/tmp/x.cif"


def test_analyzer_flags_poor_complex():
    a = StructureAnalyzer(_FakeBackend(iptm=0.2)).assess(_guide(), _target())
    assert not a.well_formed
    assert any("low interface confidence" in n for n in a.notes)


def test_backend_not_configured():
    backend = SubprocessFoldingBackend(binary="definitely-not-a-folding-binary-xyz")
    with pytest.raises(StructureNotConfigured):
        backend.fold(to_af3_json(build_complex(_guide(), _target())))
