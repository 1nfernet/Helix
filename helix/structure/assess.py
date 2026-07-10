"""Run a folding backend on an editing complex and summarize its confidence."""

from __future__ import annotations

from helix.ir.design import GuideCandidate, ResolvedTarget
from helix.ir.enums import Enzyme
from helix.structure.backend import StructureBackend
from helix.structure.complex import build_complex, to_af3_json
from helix.structure.models import StructureAssessment, StructureConfidence


class StructureAnalyzer:
    def __init__(self, backend: StructureBackend, well_formed_iptm: float = 0.5):
        self._backend = backend
        self._threshold = well_formed_iptm

    def assess(
        self,
        guide: GuideCandidate,
        target: ResolvedTarget,
        enzyme: Enzyme = Enzyme.SPCAS9,
        flank: int = 10,
    ) -> StructureAssessment:
        cx = build_complex(guide, target, enzyme, flank)
        result = self._backend.fold(to_af3_json(cx))
        confidence = StructureConfidence(
            ptm=float(result.get("ptm", 0.0)),
            iptm=float(result.get("iptm", 0.0)),
            plddt=float(result.get("plddt", 0.0)),
        )
        well_formed = confidence.iptm >= self._threshold
        notes = []
        if not well_formed:
            notes.append(
                f"low interface confidence (ipTM {confidence.iptm:.2f} < {self._threshold}); "
                "the complex may not assemble at this site."
            )
        return StructureAssessment(
            label=cx.label,
            confidence=confidence,
            well_formed=well_formed,
            structure_path=result.get("structure_path"),
            backend=self._backend.name,
            notes=notes,
        )
