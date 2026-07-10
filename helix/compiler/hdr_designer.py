"""Homology-directed repair (HDR) knock-in designer.

A precise edit — point mutation, tag, or small cassette — installed by cutting
near the target with a nuclease and supplying a *donor* (ssODN or dsDNA) whose
homology arms flank the change. Two design operations beyond guide selection:

  1. pick a cut *close* to the edit — HDR efficiency falls off sharply with the
     cut-to-edit distance, so guides that cut far away are dropped;
  2. build the donor — homology arms around the edit, plus a silent mutation that
     destroys the protospacer/PAM so the nuclease cannot re-cut the corrected allele.

Guide enumeration and on/off-target scoring are the same real logic and adapters
as the knockout designer; the edit uses the prime-edit grammar (sub / ins / del).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from helix.adapters.base import OffTargetScorer, OnTargetScorer, ScorerContextError
from helix.bio import gc_content, iter_pam_sites, reverse_complement
from helix.codons import classify_change
from helix.compiler.consequence import edit_consequence
from helix.compiler.guide_designer import _mer30
from helix.compiler.prime_editor import _label, parse_edit
from helix.ir.design import GuideCandidate, HdrDonor, ResolvedTarget
from helix.ir.enums import HDR_ARM_LENGTHS, PAM_TABLE, DonorType, Enzyme, Strand

_MAX_CUT_TO_EDIT = 30  # bp; HDR is best within ~10 bp and negligible beyond ~30


def design_hdr(
    target: ResolvedTarget,
    enzyme: Enzyme,
    edit: str,
    donor: DonorType,
    on_target: OnTargetScorer,
    off_target: OffTargetScorer,
    arm_length: Optional[int] = None,
) -> List[GuideCandidate]:
    if enzyme not in PAM_TABLE:
        raise NotImplementedError(f"No PAM spec for {enzyme}.")
    ref, alt, pos0 = parse_edit(edit)
    arm = arm_length or HDR_ARM_LENGTHS[donor]
    e = PAM_TABLE[enzyme]
    pam, slen, is_3p, coff = e["pam"], e["spacer_length"], e["pam_is_3prime"], e["cut_offset_from_pam"]
    pamlen = len(pam)
    is_spcas9 = enzyme is Enzyme.SPCAS9

    seq = target.sequence
    length = len(seq)
    out: List[GuideCandidate] = []

    def cut_of(start: int) -> int:
        return start + slen - coff if is_3p else start + coff

    for start, spacer, pam_seq in iter_pam_sites(seq, pam, slen, is_3p):
        cand = _build(target, spacer, pam_seq, Strand.PLUS, start, cut_of(start),
                      _mer30(seq, start) if is_spcas9 else "", seq, length, slen, pamlen,
                      is_3p, is_spcas9, ref, alt, pos0, donor, arm, on_target, off_target)
        if cand is not None:
            out.append(cand)

    rc = reverse_complement(seq)
    for rc_start, spacer, pam_seq in iter_pam_sites(rc, pam, slen, is_3p):
        window_offset = length - rc_start - slen
        cut = length - 1 - cut_of(rc_start)
        cand = _build(target, spacer, pam_seq, Strand.MINUS, window_offset, cut,
                      _mer30(rc, rc_start) if is_spcas9 else "", seq, length, slen, pamlen,
                      is_3p, is_spcas9, ref, alt, pos0, donor, arm, on_target, off_target)
        if cand is not None:
            out.append(cand)

    return out


def _build(target, spacer, pam, strand, window_offset, cut, mer30, seq, length,
           slen, pamlen, is_3p, is_spcas9, ref, alt, pos0, donor, arm,
           on_target, off_target) -> Optional[GuideCandidate]:
    dist = abs(cut - pos0)
    if dist > _MAX_CUT_TO_EDIT:
        return None  # cut too far from the edit to drive HDR
    try:
        on = on_target.score(spacer, mer30)
    except ScorerContextError:
        return None
    off = off_target.scan(spacer, target.genome_build)

    hdr = _build_donor(seq, length, ref, alt, pos0, strand, window_offset,
                       slen, pamlen, is_3p, is_spcas9, donor, arm, dist, target.frame)

    proximity = max(0.0, 1.0 - dist / (_MAX_CUT_TO_EDIT + 1))
    composite = on * (1.0 - off.max_cfd) * proximity
    return GuideCandidate(
        spacer=spacer, pam=pam, strand=strand,
        window_offset=window_offset, cut_site=cut,
        gc_content=round(gc_content(spacer), 3),
        on_target_score=round(on, 3), off_target=off,
        hdr=hdr, composite_score=round(composite, 4),
    )


def _pam_span(strand: Strand, window_offset: int, slen: int, pamlen: int, is_3p: bool) -> Tuple[int, int]:
    """Plus-strand coordinates of the PAM for this guide."""
    if is_3p:  # PAM 3' of the protospacer (SpCas9/SaCas9)
        return (window_offset + slen, window_offset + slen + pamlen) if strand is Strand.PLUS \
            else (window_offset - pamlen, window_offset)
    # PAM 5' of the protospacer (Cas12a)
    return (window_offset - pamlen, window_offset) if strand is Strand.PLUS \
        else (window_offset + slen, window_offset + slen + pamlen)


def _pam_block_candidates(strand: Strand, pam_span: Tuple[int, int], is_3p: bool, is_spcas9: bool):
    """Every (plus_index, new_base) single change that breaks the SpCas9 NGG PAM.

    Ordered so the historical default comes first (used when no reading frame is
    known); with a frame, the caller prefers whichever candidate is synonymous.
    """
    if not (is_3p and is_spcas9):
        return []  # only SpCas9 NGG handled automatically
    if strand is Strand.PLUS:
        g2, g3 = pam_span[0] + 1, pam_span[1] - 1  # the two G's of NGG on plus
        out = [(g3, "C")]  # default: NGG -> NGC
        out += [(g3, b) for b in ("A", "T")] + [(g2, b) for b in ("A", "C", "T")]
        return out
    c1, c2 = pam_span[0], pam_span[0] + 1  # minus PAM reads CCN on plus: the two C's
    out = [(c2, "G")]  # default
    out += [(c2, b) for b in ("A", "T")] + [(c1, b) for b in ("A", "G", "T")]
    return out


def _choose_pam_block(seq, strand, pam_span, is_3p, is_spcas9, pos0, ref_len, arm, length, frame):
    """Pick a PAM-breaking donor mutation, preferring a synonymous one when a frame is known.

    Returns (plus_index, new_base, silent) — silent is True (synonymous), False (no
    synonymous break exists in coding context), or None (no frame / non-coding PAM).
    """
    cands = _pam_block_candidates(strand, pam_span, is_3p, is_spcas9)
    valid = [
        (i, b) for (i, b) in cands
        if 0 <= i < length and (pos0 - arm) <= i < (pos0 + ref_len + arm) and seq[i] != b
    ]
    if not valid:
        return None
    if frame is None:
        return (valid[0][0], valid[0][1], None)
    coding_seen = False
    for i, b in valid:
        call = classify_change(seq, frame, i, b)
        if call is None:
            continue
        coding_seen = True
        if call["kind"] == "synonymous":
            return (i, b, True)
    return (valid[0][0], valid[0][1], False if coding_seen else None)


def _build_donor(seq, length, ref, alt, pos0, strand, window_offset, slen, pamlen,
                 is_3p, is_spcas9, donor, arm, dist, frame) -> HdrDonor:
    ref_len = 0 if ref == "-" else len(ref)
    ins = "" if alt == "-" else alt

    proto = (window_offset, window_offset + slen)
    pam_span = _pam_span(strand, window_offset, slen, pamlen, is_3p)
    footprint = (min(proto[0], pam_span[0]), max(proto[1], pam_span[1]))
    edit_hits = pos0 < footprint[1] and pos0 + ref_len > footprint[0]

    bases = list(seq)
    silent_pam_block = None
    if edit_hits:
        pam_disrupted = True
        recut_note = "The edit lands in the protospacer/PAM, so the corrected allele cannot be re-cut."
    else:
        block = _choose_pam_block(seq, strand, pam_span, is_3p, is_spcas9,
                                  pos0, ref_len, arm, length, frame)
        if block is not None:
            idx, base, silent_pam_block = block
            bases[idx] = base
            pam_disrupted = True
            if silent_pam_block is True:
                recut_note = "A synonymous PAM-blocking mutation was added to the donor to prevent re-cutting."
            elif silent_pam_block is False:
                recut_note = ("A PAM-blocking mutation was added to prevent re-cutting; no synonymous option "
                              "breaks the PAM here, so it changes an amino acid — review before use.")
            else:
                recut_note = ("A silent PAM-blocking mutation was added to the donor to prevent re-cutting "
                              "(set target.frame to verify it is synonymous in a coding region).")
        else:
            pam_disrupted = False
            recut_note = "Cut does not overlap the edit; add a PAM-blocking mutation to the donor to prevent re-cutting."

    core = bases[:pos0] + list(ins) + bases[pos0 + ref_len:]
    ins_len = len(ins)
    lo = max(0, pos0 - arm)
    hi = min(len(core), pos0 + ins_len + arm)
    left_arm = "".join(core[lo:pos0])
    payload = "".join(core[pos0:pos0 + ins_len])
    right_arm = "".join(core[pos0 + ins_len:hi])

    return HdrDonor(
        donor_type=donor.value,
        strand="-" if strand is Strand.PLUS else "+",  # non-target strand (ssODN heuristic)
        left_arm=left_arm,
        insert=payload,
        right_arm=right_arm,
        sequence=left_arm + payload + right_arm,
        edit=_label(ref, alt, pos0),
        edit_pos=pos0,
        cut_to_edit_distance=dist,
        arm_length=arm,
        pam_disrupted=pam_disrupted,
        recut_note=recut_note,
        consequence=edit_consequence(seq, frame, pos0, ref, alt),
        silent_pam_block=silent_pam_block,
    )
