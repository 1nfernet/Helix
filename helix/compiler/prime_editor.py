"""Prime-editing designer.

Designs pegRNAs for substitutions, insertions and deletions: a nicking SpCas9
guide plus a 3' extension = RTT (encodes the edit) + PBS (binds the nicked 3' end),
optionally with a PE3 second nick on the opposite strand to raise efficiency.
Searches nicking guides on **both strands**, requires a 3' homology arm, and is
built so the installed edit is provably correct (round-trip verified in tests).

Edit syntax: ``REF>ALT @ POS`` (1-based). Use ``-`` for an empty side:
``->AAC @ 12`` inserts AAC; ``AC>- @ 12`` deletes AC.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from helix.adapters.base import OffTargetScorer, OnTargetScorer, ScorerContextError
from helix.adapters.prime_edit_model import HeuristicPrimeEditBackend, PrimeEditBackend
from helix.bio import iter_pam_sites, reverse_complement
from helix.compiler.consequence import edit_consequence
from helix.compiler.guide_designer import _mer30
from helix.ir.design import PrimeEditCandidate, ResolvedTarget
from helix.ir.enums import Enzyme, Strand

_PAM = "NGG"
_SLEN = 20
_CUT_OFFSET = 3  # nick 3 nt 5' of the PAM
_MIN_HOMOLOGY_3P = 5  # matched genome bases required 3' of the edit within the RTT
_PE3_MIN, _PE3_MAX, _PE3_OPT = 40, 90, 50  # PE3 nick distance window from the edit
_EDIT_RE = re.compile(r"([ACGT]+|-)\s*>\s*([ACGT]+|-)\s*@\s*(\d+)", re.I)


def parse_edit(edit: str) -> Tuple[str, str, int]:
    """'A>G @ 12' -> ('A','G',11); '->AAC @ 12' insertion; 'AC>- @ 12' deletion."""
    m = _EDIT_RE.search(edit or "")
    if not m:
        raise ValueError(f"prime edit must look like 'A>G @ 12' (or '->AAC', 'AC>-'), got {edit!r}")
    ref, alt = m.group(1).upper(), m.group(2).upper()
    if ref == "-" and alt == "-":
        raise ValueError("prime edit must change something")
    return ref, alt, int(m.group(3)) - 1


def _label(ref: str, alt: str, pos0: int) -> str:
    if ref == "-":
        return f"ins {alt} @ {pos0 + 1}"
    if alt == "-":
        return f"del {ref} @ {pos0 + 1}"
    return f"{ref}>{alt} @ {pos0 + 1}"


def design_prime_edits(
    target: ResolvedTarget,
    enzyme: Enzyme,
    edit: str,
    on_target: OnTargetScorer,
    off_target: OffTargetScorer,
    model: Optional[PrimeEditBackend] = None,
    pbs_len: int = 13,
    rtt_len: int = 16,
) -> List[PrimeEditCandidate]:
    if enzyme is not Enzyme.SPCAS9:
        raise NotImplementedError("Prime editing supports SpCas9 nickases only.")
    model = model or HeuristicPrimeEditBackend()
    ref, alt, pos0 = parse_edit(edit)

    seq = target.sequence
    L = len(seq)
    ref_len = 0 if ref == "-" else len(ref)
    alt_content = "" if alt == "-" else alt
    content_len = len(alt_content)
    if ref != "-" and seq[pos0 : pos0 + ref_len] != ref:
        raise ValueError(
            f"edit ref {ref!r} does not match target at position {pos0 + 1} "
            f"({seq[pos0:pos0 + ref_len]!r})."
        )

    edited = seq[:pos0] + alt_content + seq[pos0 + ref_len:]
    Lp = len(edited)
    label = _label(ref, alt, pos0)

    # PE3 nicks the strand opposite the pegRNA. Precompute the best on each strand.
    pe3_on_minus = _best_pe3(seq, "minus", pos0, L)  # for plus-strand pegRNAs
    pe3_on_plus = _best_pe3(seq, "plus", pos0, L)  # for minus-strand pegRNAs

    out: List[PrimeEditCandidate] = []
    out += _design_on_strand(target, seq, edited, pos0, content_len, Strand.PLUS,
                             pbs_len, rtt_len, label, model, on_target, off_target, pe3_on_minus)
    rc, edited_rc = reverse_complement(seq), reverse_complement(edited)
    out += _design_on_strand(target, rc, edited_rc, Lp - pos0 - content_len, content_len, Strand.MINUS,
                             pbs_len, rtt_len, label, model, on_target, off_target, pe3_on_plus)

    # The protein consequence is a property of the edit itself (ref>alt @ pos0 in
    # window/coding coords), identical across nicking-guide candidates.
    consequence = edit_consequence(seq, target.frame, pos0, ref, alt)
    if consequence is not None:
        for c in out:
            c.consequence = consequence
    return out


def _design_on_strand(target, local, edited_local, edit0, content_len, strand, pbs_len, rtt_len,
                      label, model, on_target, off_target, pe3) -> List[PrimeEditCandidate]:
    L = len(local)
    Lloc = len(edited_local)
    out: List[PrimeEditCandidate] = []
    for start, spacer, pam_seq in iter_pam_sites(local, _PAM, _SLEN, True):
        nick = start + _SLEN - _CUT_OFFSET
        if nick > edit0:  # edit must be downstream of the nick
            continue
        if edit0 + content_len + _MIN_HOMOLOGY_3P > nick + rtt_len:  # 3' homology arm
            continue
        if nick - pbs_len < 0 or nick + rtt_len > Lloc:
            continue

        rtt = reverse_complement(edited_local[nick : nick + rtt_len])
        pbs = reverse_complement(local[nick - pbs_len : nick])
        nick_plus = nick if strand is Strand.PLUS else L - nick

        cand = _build(target, spacer, pam_seq, strand, nick_plus, rtt, pbs, label,
                      _mer30(local, start), model, on_target, off_target, pe3)
        if cand is not None:
            out.append(cand)
    return out


def _best_pe3(seq: str, side: str, edit_pos0: int, L: int):
    """Best opposite-strand nick 40-90 nt from the edit (closest to ~50)."""
    if side == "plus":
        sites = ((start + _SLEN - _CUT_OFFSET, spacer) for start, spacer, _ in iter_pam_sites(seq, _PAM, _SLEN, True))
    else:
        rc = reverse_complement(seq)
        sites = ((L - (s + _SLEN - _CUT_OFFSET), spacer) for s, spacer, _ in iter_pam_sites(rc, _PAM, _SLEN, True))
    best = None
    best_score = None
    for nick_plus, spacer in sites:
        d = abs(nick_plus - edit_pos0)
        if _PE3_MIN <= d <= _PE3_MAX:
            score = abs(d - _PE3_OPT)
            if best_score is None or score < best_score:
                best, best_score = (spacer, nick_plus), score
    return best


def _build(target, spacer, pam, strand, nick_plus, rtt, pbs, label, mer, model,
           on_target, off_target, pe3) -> Optional[PrimeEditCandidate]:
    try:
        on = on_target.score(spacer, mer)
    except ScorerContextError:
        return None
    off = off_target.scan(spacer, target.genome_build)
    pred = model.predict(spacer, pbs, rtt, label)
    pe3_spacer, pe3_pos = pe3 if pe3 else (None, None)
    return PrimeEditCandidate(
        spacer=spacer,
        pam=pam,
        strand=strand,
        nick_position=nick_plus,
        pbs=pbs,
        rtt=rtt,
        peg_extension=rtt + pbs,
        edit=label,
        on_target_score=round(on, 3),
        predicted_efficiency=pred.efficiency,
        predictor=pred.predictor,
        pe3_nick_spacer=pe3_spacer,
        pe3_nick_position=pe3_pos,
        composite_score=round(on * (1.0 - off.max_cfd) * pred.efficiency, 4),
    )
