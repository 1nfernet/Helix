"""Enumerate and score candidate guides across both strands.

The enumeration is real SpCas9 logic: every NGG site on the plus and minus
strands within the edit window yields a 20 nt protospacer, mapped back to
plus-strand window coordinates. Scoring is delegated to the on-target,
off-target, and repair adapters — so the *design logic* is fixed and testable
while the *models* are swappable.

Each guide is scored on its own strand, so on-target models receive the correct
30-mer (4 bp 5' context + 20 bp protospacer + 3 bp PAM + 3 bp 3' context). Guides
too close to the window edge to form that context are dropped rather than scored
on fabricated flanks (see :class:`ScorerContextError`).
"""

from __future__ import annotations

from typing import List, Optional

from helix.adapters.base import (
    OffTargetScorer,
    OnTargetScorer,
    RepairOutcomePredictor,
    ScorerContextError,
)
from helix.bio import gc_content, iter_pam_sites, reverse_complement
from helix.ir.design import GuideCandidate, ResolvedTarget
from helix.ir.enums import PAM_TABLE, Enzyme, Strand

_REPAIR_FLANK = 40  # nt of context each side of the cut for repair prediction
_MER_5P = 4  # 5' flank of the on-target 30-mer
_MER_3P = 6  # PAM (3) + 3' flank (3) after the protospacer


def design_guides(
    target: ResolvedTarget,
    enzyme: Enzyme,
    on_target: OnTargetScorer,
    off_target: OffTargetScorer,
    repair: RepairOutcomePredictor,
) -> List[GuideCandidate]:
    if enzyme not in PAM_TABLE:
        raise NotImplementedError(f"No PAM spec for {enzyme}.")
    e = PAM_TABLE[enzyme]
    pam, slen, is_3p, coff = e["pam"], e["spacer_length"], e["pam_is_3prime"], e["cut_offset_from_pam"]
    is_spcas9 = enzyme is Enzyme.SPCAS9

    seq = target.sequence
    length = len(seq)
    candidates: List[GuideCandidate] = []

    def cut_of(start: int) -> int:
        return start + slen - coff if is_3p else start + coff

    # --- plus strand ----------------------------------------------------
    for start, spacer, pam_seq in iter_pam_sites(seq, pam, slen, is_3p):
        guide = _build(
            target, spacer, pam_seq, Strand.PLUS, start, cut_of(start), seq, length,
            _mer30(seq, start) if is_spcas9 else "", on_target, off_target, repair,
        )
        if guide is not None:
            candidates.append(guide)

    # --- minus strand (enumerate on the reverse complement, map coords back) --
    rc = reverse_complement(seq)
    for rc_start, spacer, pam_seq in iter_pam_sites(rc, pam, slen, is_3p):
        window_offset = length - rc_start - slen
        cut = length - 1 - cut_of(rc_start)
        guide = _build(
            target, spacer, pam_seq, Strand.MINUS, window_offset, cut, seq, length,
            _mer30(rc, rc_start) if is_spcas9 else "", on_target, off_target, repair,
        )
        if guide is not None:
            candidates.append(guide)

    return candidates


def enumerate_scored(
    target: ResolvedTarget,
    enzyme: Enzyme,
    on_target: OnTargetScorer,
    off_target: OffTargetScorer,
) -> List[GuideCandidate]:
    """Enumerate guides with on/off-target scores only (no repair prediction).

    Shared by the deletion and CRISPRi/a designers, which need the guide set and
    positions but not DSB-repair outcomes.
    """
    if enzyme not in PAM_TABLE:
        raise NotImplementedError(f"No PAM spec for {enzyme}.")
    e = PAM_TABLE[enzyme]
    pam, slen, is_3p, coff = e["pam"], e["spacer_length"], e["pam_is_3prime"], e["cut_offset_from_pam"]
    is_spcas9 = enzyme is Enzyme.SPCAS9
    seq = target.sequence
    length = len(seq)
    out: List[GuideCandidate] = []

    def cut_of(start: int) -> int:
        return start + slen - coff if is_3p else start + coff

    def add(spacer, pam_seq, strand, window_offset, cut, mer):
        try:
            on = on_target.score(spacer, mer)
        except ScorerContextError:
            return
        off = off_target.scan(spacer, target.genome_build)
        out.append(GuideCandidate(
            spacer=spacer, pam=pam_seq, strand=strand, window_offset=window_offset, cut_site=cut,
            gc_content=round(gc_content(spacer), 3), on_target_score=round(on, 3), off_target=off,
            composite_score=round(on * (1.0 - off.max_cfd), 4),
        ))

    for start, spacer, pam_seq in iter_pam_sites(seq, pam, slen, is_3p):
        add(spacer, pam_seq, Strand.PLUS, start, cut_of(start), _mer30(seq, start) if is_spcas9 else "")
    rc = reverse_complement(seq)
    for rc_start, spacer, pam_seq in iter_pam_sites(rc, pam, slen, is_3p):
        add(spacer, pam_seq, Strand.MINUS, length - rc_start - slen,
            length - 1 - cut_of(rc_start), _mer30(rc, rc_start) if is_spcas9 else "")
    return out


def _mer30(strand_seq: str, spacer_start: int) -> str:
    """The SpCas9 30-mer around a site, on its own strand ('' if it runs off an edge)."""
    lo = spacer_start - _MER_5P
    hi = spacer_start + 20 + _MER_3P  # 4 + 20 (SpCas9 spacer) + 6 = 30
    if lo < 0 or hi > len(strand_seq):
        return ""
    return strand_seq[lo:hi]


def _build(target, spacer, pam, strand, window_offset, cut, seq, length,
           mer30, on_target, off_target, repair) -> Optional[GuideCandidate]:
    rlo = max(0, cut - _REPAIR_FLANK)
    rhi = min(length, cut + _REPAIR_FLANK)
    repair_seq = seq[rlo:rhi]
    local_cut = cut - rlo

    # A per-guide context failure (e.g. too close to the window edge for a model's
    # required flanks) drops just that guide. Config errors (no genome, no inDelphi)
    # are not ScorerContextError and correctly propagate.
    try:
        on = on_target.score(spacer, mer30)
        off = off_target.scan(spacer, target.genome_build)
        rep = repair.predict(repair_seq, local_cut)
    except ScorerContextError:
        return None

    return GuideCandidate(
        spacer=spacer,
        pam=pam,
        strand=strand,
        window_offset=window_offset,
        cut_site=cut,
        gc_content=round(gc_content(spacer), 3),
        on_target_score=round(on, 3),
        off_target=off,
        repair=rep,
        composite_score=round(on * (1.0 - off.max_cfd), 4),
    )
