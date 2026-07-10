"""Reading-frame / genetic-code utilities for protein-consequence calls.

The window sequence is treated as the coding (sense) strand; ``frame`` is the
0-based codon phase of window position 0 (i.e. window[frame] starts a codon).
Everything here is pure and deterministic — the standard genetic code — so the
"is my edit synonymous / missense / premature-stop?" question is answered without
any external tool.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List, Optional, Sequence, Tuple

STOP = "*"

# Standard genetic code (NCBI table 1). Stop codons -> '*'.
GENETIC_CODE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": STOP, "TAG": STOP,
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": STOP, "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def translate_codon(codon: str) -> str:
    """One-letter amino acid for a codon; 'X' if it contains a non-ACGT base."""
    return GENETIC_CODE.get(codon.upper(), "X")


def codon_span(pos: int, frame: int) -> Optional[Tuple[int, int, int]]:
    """(codon_start, codon_index, offset_in_codon) for window position ``pos``.

    ``frame`` is the phase of window position 0. Returns None if ``pos`` sits
    before the first whole codon.
    """
    rel = pos - (frame % 3)
    if rel < 0:
        return None
    ci = rel // 3
    start = (frame % 3) + ci * 3
    return start, ci, pos - start


def _kind(ref_aa: str, alt_aa: str) -> str:
    if ref_aa == alt_aa:
        return "synonymous"
    if alt_aa == STOP:
        return "nonsense"
    if ref_aa == STOP:
        return "stop-loss"
    return "missense"


def classify_changes(window: str, frame: int, changes: Sequence[Tuple[int, str]]) -> List[dict]:
    """Classify substitutions, grouping changes that fall in the SAME codon.

    ``changes`` are (window_pos, new_base) substitutions on the coding strand.
    Base editors edit several bases in one window and two can share a codon, so
    each affected codon is classified once against its *combined* mutant — not per
    base. Returns one dict per readable affected codon (in codon order); codons
    that run off the window or contain non-ACGT bases are skipped.
    """
    by_codon: dict = defaultdict(list)
    for pos, alt in changes:
        span = codon_span(pos, frame)
        if span is None:
            continue
        start, ci, off = span
        by_codon[start].append((ci, off, alt.upper()))

    out: List[dict] = []
    for start in sorted(by_codon):
        if start < 0 or start + 3 > len(window):
            continue
        ref_codon = window[start : start + 3].upper()
        if any(b not in "ACGT" for b in ref_codon):
            continue
        mut = list(ref_codon)
        ci = by_codon[start][0][0]
        ok = True
        for _ci, off, alt in by_codon[start]:
            if alt not in "ACGT":
                ok = False
                break
            mut[off] = alt
        if not ok:
            continue
        mut_codon = "".join(mut)
        ref_aa = translate_codon(ref_codon)
        alt_aa = translate_codon(mut_codon)
        out.append({
            "ref_codon": ref_codon, "alt_codon": mut_codon,
            "ref_aa": ref_aa, "alt_aa": alt_aa, "codon_index": ci,
            "kind": _kind(ref_aa, alt_aa),
        })
    return out


def classify_change(window: str, frame: int, pos: int, alt: str) -> Optional[dict]:
    """Classify a single-base substitution window[pos] -> alt in coding context.

    Returns None when the codon can't be read (before frame start, or runs off the
    window edge, or the codon has non-ACGT bases). Otherwise a dict with the ref/alt
    amino acids, codon index, and a ``kind`` in
    {synonymous, missense, nonsense, stop-loss}.
    """
    calls = classify_changes(window, frame, [(pos, alt)])
    return calls[0] if calls else None
