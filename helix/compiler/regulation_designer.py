"""CRISPRi / CRISPRa designer — dCas9 transcriptional regulation (no cut).

A catalytically-dead Cas9 fused to a repressor (KRAB) or activator (VPR/SAM)
silences or activates a gene when guided to the right window around the
transcription start site (TSS):

  * CRISPRi — strongest just downstream of the TSS (roughly −50 to +300 bp);
  * CRISPRa — strongest in the upstream promoter (roughly −400 to −50 bp).

Each guide is scored by its position relative to the TSS (a data-driven efficacy
window) times its on-target binding and off-target specificity. No DSB, so no
repair outcome.
"""

from __future__ import annotations

from typing import List

from helix.adapters.base import OffTargetScorer, OnTargetScorer
from helix.compiler.guide_designer import enumerate_scored
from helix.ir.design import GuideCandidate, RegulationOutcome, ResolvedTarget
from helix.ir.enums import Enzyme, Modality, PAM_TABLE

# Optimal offset window (bp from TSS): − upstream, + downstream.
_WINDOWS = {Modality.CRISPRI: (-50, 300), Modality.CRISPRA: (-400, -50)}


def _activity(offset: int, lo: int, hi: int) -> float:
    """Positional efficacy 0..1: a plateau-topped peak inside the window, small outside."""
    mid, half = (lo + hi) / 2.0, (hi - lo) / 2.0
    if lo <= offset <= hi:
        return round(0.5 + 0.5 * (1 - abs(offset - mid) / half), 3)
    d = min(abs(offset - lo), abs(offset - hi))
    return round(max(0.0, 0.3 * (1 - d / 200.0)), 3)


def design_regulation(
    target: ResolvedTarget,
    mode: Modality,
    on_target: OnTargetScorer,
    off_target: OffTargetScorer,
    tss: int = None,
) -> List[GuideCandidate]:
    length = len(target.sequence)
    tss0 = (tss - 1) if tss else length // 2
    lo, hi = _WINDOWS[mode]
    slen = PAM_TABLE[Enzyme.DCAS9]["spacer_length"]

    guides = enumerate_scored(target, Enzyme.DCAS9, on_target, off_target)
    for g in guides:
        center = g.window_offset + slen // 2  # protospacer centre = binding site
        offset = center - tss0
        activity = _activity(offset, lo, hi)
        g.regulation = RegulationOutcome(
            mode=mode.value, tss_offset=offset, activity_score=activity, optimal=lo <= offset <= hi,
        )
        g.composite_score = round(g.on_target_score * (1.0 - g.off_target.max_cfd) * activity, 4)
    return guides
