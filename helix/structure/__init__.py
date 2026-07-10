"""Structural simulation of the Cas9-gRNA-DNA complex.

An opt-in, heavy stage: assemble the editing complex (SpCas9 protein + sgRNA +
target DNA duplex) into a folding-tool input, run a structure predictor
(AlphaFold3 / Boltz) behind an injectable backend, and summarize its confidence
(pTM / ipTM / pLDDT) into a structural assessment. Useful for hard off-target
calls where a mismatched target may still (or may not) form a stable R-loop.

The complex assembly is deterministic and tested; the predictor — like the other
heavy tools — sits behind an injectable subprocess backend with a clear
not-configured error, so this is unit-tested offline.
"""

from helix.structure.assess import StructureAnalyzer
from helix.structure.backend import StructureNotConfigured, SubprocessFoldingBackend
from helix.structure.complex import build_complex, to_af3_json, to_rna
from helix.structure.models import ComplexSpec, StructureAssessment, StructureConfidence

__all__ = [
    "StructureAnalyzer",
    "SubprocessFoldingBackend",
    "StructureNotConfigured",
    "build_complex",
    "to_af3_json",
    "to_rna",
    "ComplexSpec",
    "StructureAssessment",
    "StructureConfidence",
]
