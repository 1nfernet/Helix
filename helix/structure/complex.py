"""Assemble a Cas9-gRNA-DNA complex and render a folding-tool input.

Deterministic and dependency-free: given a designed guide and its target window,
build the SpCas9 protein + sgRNA (spacer + scaffold) + target DNA duplex, and emit
an AlphaFold3-style input JSON (Boltz can consume a converted form).
"""

from __future__ import annotations

from helix.bio import normalize, reverse_complement
from helix.ir.design import GuideCandidate, ResolvedTarget
from helix.ir.enums import Enzyme
from helix.structure.data.spcas9 import SGRNA_SCAFFOLD, SPCAS9_PROTEIN
from helix.structure.models import ComplexSpec

_PROTOSPACER_PAM = 23  # SpCas9: 20 nt protospacer + 3 nt PAM
_DEFAULT_FLANK = 10


def to_rna(dna: str) -> str:
    return normalize(dna).replace("T", "U")


def build_complex(
    guide: GuideCandidate,
    target: ResolvedTarget,
    enzyme: Enzyme = Enzyme.SPCAS9,
    flank: int = _DEFAULT_FLANK,
) -> ComplexSpec:
    if enzyme is not Enzyme.SPCAS9:
        raise NotImplementedError("Structural assembly is wired for SpCas9 only.")
    seq = target.sequence
    start = guide.window_offset
    lo = max(0, start - flank)
    hi = min(len(seq), start + _PROTOSPACER_PAM + flank)
    sense = seq[lo:hi]

    return ComplexSpec(
        protein=SPCAS9_PROTEIN,
        guide_rna=to_rna(guide.spacer + SGRNA_SCAFFOLD),
        target_dna_sense=sense,
        target_dna_antisense=reverse_complement(sense),
        label=f"{target.gene}:{guide.spacer}",
    )


def to_af3_json(cx: ComplexSpec) -> dict:
    """AlphaFold3 input JSON: protein + sgRNA + double-stranded target DNA."""
    return {
        "name": cx.label,
        "modelSeeds": [1],
        "sequences": [
            {"protein": {"id": "A", "sequence": cx.protein}},
            {"rna": {"id": "B", "sequence": cx.guide_rna}},
            {"dna": {"id": "C", "sequence": cx.target_dna_sense}},
            {"dna": {"id": "D", "sequence": cx.target_dna_antisense}},
        ],
        "dialect": "alphafold3",
        "version": 1,
    }
