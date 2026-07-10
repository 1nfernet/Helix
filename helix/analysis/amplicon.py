"""Offline amplicon editing analysis — no external tools.

An anchor-based indel caller: locate conserved flanks just outside the cut in each
read, and the change in the distance between them is the net indel; reads whose
middle differs without an indel are substitutions (base/prime edits). Good enough
to quantify editing efficiency + a frameshift fraction for the design→validate loop
when CRISPResso2 isn't installed. A synthetic-read generator backs the UI demo.
"""

from __future__ import annotations

import random
from typing import List, Tuple

from helix.analysis.models import EditingAnalysis


def _clean(s: str) -> str:
    return "".join(str(s).upper().split())


def _find_near(hay: str, needle: str, expected: int, start: int = 0) -> int:
    """Index of the occurrence of `needle` closest to `expected` (robust to repeats)."""
    idx, best, best_d = hay.find(needle, start), -1, 1 << 30
    while idx != -1:
        d = abs(idx - expected)
        if d < best_d:
            best, best_d = idx, d
        idx = hay.find(needle, idx + 1)
    return best


def parse_reads(text: str) -> List[str]:
    """Extract read sequences from FASTQ, FASTA, or one-per-line text."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    if lines[0].startswith("@") and len(lines) >= 4 and lines[2].startswith("+"):
        return [_clean(x) for x in lines[1::4]]  # FASTQ: 2nd line of each 4-line record
    if lines[0].startswith(">"):
        reads, cur = [], ""
        for ln in lines:
            if ln.startswith(">"):
                if cur:
                    reads.append(cur)
                cur = ""
            else:
                cur += _clean(ln)
        if cur:
            reads.append(cur)
        return reads
    return [_clean(ln) for ln in lines if set(_clean(ln)) <= set("ACGTN")]


def analyze_amplicon(
    reference: str, reads: List[str], cut_pos: int = None, anchor: int = 15, buffer: int = 12
) -> Tuple[EditingAnalysis, List[dict]]:
    ref = _clean(reference)
    reads = [_clean(r) for r in reads if r and r.strip()]
    if not ref or not reads:
        raise ValueError("provide a reference amplicon and at least one read")
    n = len(ref)
    if cut_pos is None:
        cut_pos = n // 2
    cut_pos = max(anchor + buffer, min(n - anchor - buffer, cut_pos))
    l2, l1 = cut_pos - buffer, cut_pos - buffer - anchor
    r1, r2 = cut_pos + buffer, cut_pos + buffer + anchor
    left, right, ref_mid = ref[l1:l2], ref[r1:r2], ref[l2:r1]
    ref_between = r1 - l2

    aligned = modified = ins = dele = subs = frameshift = 0
    spectrum: dict = {}
    for read in reads:
        li = _find_near(read, left, l1)
        if li < 0:
            continue
        start = li + len(left)
        ri = _find_near(read, right, r1, start=start)
        if ri < 0:
            continue
        aligned += 1
        indel = (ri - start) - ref_between
        if indel != 0:
            modified += 1
            spectrum[indel] = spectrum.get(indel, 0) + 1
            if indel > 0:
                ins += 1
            else:
                dele += 1
            if indel % 3 != 0:
                frameshift += 1
        elif read[start:ri] != ref_mid:
            modified += 1
            subs += 1

    if aligned == 0:
        raise ValueError("no reads aligned to the amplicon — check the reference/reads")
    indel_edits = ins + dele
    analysis = EditingAnalysis(
        editing_efficiency=round(modified / aligned, 3),
        reads_aligned=aligned, modified_reads=modified, unmodified_reads=aligned - modified,
        insertions=ins, deletions=dele, substitutions=subs,
        frameshift_fraction=round(frameshift / indel_edits, 3) if indel_edits else None,
        analyzer="helix_amplicon_v1",
    )
    top = sorted(spectrum.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    return analysis, [{"indel": k, "count": v} for k, v in top]


def synthetic_reads(
    reference: str, cut_pos: int, n: int = 120, edit_rate: float = 0.6, seed: int = 1, mode: str = "indel"
) -> List[str]:
    """Example amplicon reads for the demo: NHEJ-like indels (``mode='indel'`` — KO/HDR/
    deletion) or window substitutions (``mode='sub'`` — base/prime editing)."""
    ref = _clean(reference)
    rng = random.Random(seed)
    c = max(1, min(len(ref) - 1, cut_pos))
    reads = []
    for _ in range(n):
        if rng.random() >= edit_rate:
            reads.append(ref)
        elif mode == "sub":
            pos = max(0, min(len(ref) - 1, c + rng.randint(-2, 2)))
            alt = rng.choice([b for b in "ACGT" if b != ref[pos]])
            reads.append(ref[:pos] + alt + ref[pos + 1:])
        else:
            size = rng.choice([-9, -6, -4, -3, -2, -1, -1, 1, 1, 2, 3])  # deletions dominate
            if size < 0:
                reads.append(ref[: c + size] + ref[c:])
            else:
                reads.append(ref[:c] + "".join(rng.choice("ACGT") for _ in range(size)) + ref[c:])
    return reads
