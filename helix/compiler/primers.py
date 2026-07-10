"""Design a simple validation amplicon around the edit site.

A deterministic placeholder for a real primer designer (Primer3): it picks 20 nt
flanks so the cut site sits roughly central in the amplicon. Enough to make the
end-to-end 'design -> validate' story concrete; swap in Primer3 for Tm/specificity.
"""

from __future__ import annotations

from typing import List, Optional

from helix.bio import reverse_complement
from helix.ir.design import GuideCandidate, ResolvedTarget, ValidationPrimers

_PRIMER_LEN = 20
_TARGET_FLANK = 100  # desired distance from cut to each primer


def design_validation_primers(
    target: ResolvedTarget, selected: List[GuideCandidate]
) -> Optional[ValidationPrimers]:
    if not selected:
        return None
    seq = target.sequence
    n = len(seq)
    cut = selected[0].cut_site

    flank = min(_TARGET_FLANK, cut, n - cut - _PRIMER_LEN)
    if flank < _PRIMER_LEN:
        return ValidationPrimers(
            forward="", reverse="", amplicon_length=0,
            note="Edit window too short to place flanking primers; widen the target.",
        )

    fwd_start = cut - flank
    rev_end = cut + flank + _PRIMER_LEN
    forward = seq[fwd_start : fwd_start + _PRIMER_LEN]
    reverse = reverse_complement(seq[rev_end - _PRIMER_LEN : rev_end])
    return ValidationPrimers(
        forward=forward,
        reverse=reverse,
        amplicon_length=rev_end - fwd_start,
        note="Amplicon centred on the top guide's cut site (analyse with CRISPResso2).",
    )
