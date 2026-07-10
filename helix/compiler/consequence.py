"""Translate DNA edits into protein-level consequences.

Given a reading frame (the phase of window position 0, with the window taken as
the coding/sense strand), classify prime/HDR substitutions, small indels, and
base-editing windows as synonymous / missense / nonsense / stop-loss / frameshift.
This answers the molecular biologist's first question about any edit: *does it
change the protein, and how?*
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from helix.codons import classify_change, classify_changes
from helix.ir.design import ProteinConsequence

# Severity ordering so a base-editing window (many edited bases) can report its
# single most consequential change as the headline.
_SEVERITY = {"nonsense": 4, "stop-loss": 3, "missense": 2, "synonymous": 1}

_KIND_TAIL = {
    "missense": "missense",
    "nonsense": "premature STOP",
    "stop-loss": "stop lost",
}


def _label(kind: str, ref_aa: str, alt_aa: str) -> str:
    if kind == "synonymous":
        return "silent (synonymous)"
    return f"{ref_aa or '?'}>{alt_aa or '?'} {_KIND_TAIL.get(kind, kind)}"


def _from_call(call: dict) -> ProteinConsequence:
    return ProteinConsequence(
        kind=call["kind"],
        ref_aa=call["ref_aa"],
        alt_aa=call["alt_aa"],
        codon_change=f"{call['ref_codon']}>{call['alt_codon']}",
        label=_label(call["kind"], call["ref_aa"], call["alt_aa"]),
    )


def _indel_consequence(ref: str, alt: str) -> Optional[ProteinConsequence]:
    """Frameshift vs in-frame indel — determined purely by the length change."""
    rlen = 0 if ref == "-" else len(ref)
    alen = 0 if alt == "-" else len(alt)
    delta = alen - rlen
    if delta == 0:
        return None
    if delta % 3 != 0:
        return ProteinConsequence(
            kind="frameshift", ref_aa="", alt_aa="", codon_change="",
            label=f"frameshift ({'+' if delta > 0 else ''}{delta} nt)",
        )
    kind = "in-frame insertion" if delta > 0 else "in-frame deletion"
    return ProteinConsequence(
        kind="in-frame-indel", ref_aa="", alt_aa="", codon_change="",
        label=f"{kind} ({abs(delta) // 3} codon(s))",
    )


def edit_consequence(window: str, frame: Optional[int], pos0: int, ref: str, alt: str) -> Optional[ProteinConsequence]:
    """Consequence of a prime/HDR edit ``ref>alt`` at 0-based window position ``pos0``.

    Returns None when no frame is known (we don't assume the region is coding).
    Single-base substitutions get a codon-level call; indels get a frameshift /
    in-frame-indel call from the length change.
    """
    if frame is None:
        return None
    is_sub = ref not in ("-", "") and alt not in ("-", "") and len(ref) == len(alt)
    if is_sub and len(ref) == 1:
        call = classify_change(window, frame, pos0, alt)
        return _from_call(call) if call else None
    if is_sub:
        # equal-length multi-base substitution: classify each position, keep the worst.
        return _worst_over(window, frame, [(pos0 + i, alt[i]) for i in range(len(alt))])
    return _indel_consequence(ref, alt)


def _worst_over(window: str, frame: int, changes: Sequence[Tuple[int, str]]) -> Optional[ProteinConsequence]:
    # Group by codon so two edits in one codon are scored as their combined mutant.
    calls = classify_changes(window, frame, list(changes))
    if not calls:
        return None
    calls.sort(key=lambda c: _SEVERITY.get(c["kind"], 0), reverse=True)
    top = _from_call(calls[0])
    nonsyn = [c for c in calls if c["kind"] != "synonymous"]
    if len(calls) > 1:
        top.note = f"{len(nonsyn)} of {len(calls)} edited codons alter the protein"
    return top


def base_edit_consequence(
    window: str, frame: Optional[int], changes: List[Tuple[int, str]]
) -> Optional[ProteinConsequence]:
    """Headline consequence for a base-editing window.

    ``changes`` are window-level (coding-strand) ``(pos0, new_base)`` edits — one
    per edited base, already strand-resolved by the caller. Reports the most severe
    codon change (a premature STOP is the notable case: iSTOP knockout), noting how
    many edited codons alter the protein.
    """
    if frame is None or not changes:
        return None
    return _worst_over(window, frame, changes)
