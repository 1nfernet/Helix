"""Small, dependency-free sequence-biology helpers.

Deliberately plain functions with no I/O so they are trivial to unit-test and
reuse from both adapters and the compiler. Nothing here reaches the network or
the LLM.
"""

from __future__ import annotations

from typing import Iterator, Tuple

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")

# IUPAC nucleotide codes -> the set of bases they match (for PAM matching).
IUPAC = {
    "A": "A", "C": "C", "G": "G", "T": "T",
    "R": "AG", "Y": "CT", "S": "GC", "W": "AT", "K": "GT", "M": "AC",
    "B": "CGT", "D": "AGT", "H": "ACT", "V": "ACG", "N": "ACGT",
}

# Recognition sites for restriction enzymes commonly avoided in guide/cloning
# design. Extend as needed; the compiler reads this table by name.
RESTRICTION_SITES = {
    "BsaI": "GGTCTC",
    "BsmBI": "CGTCTC",
    "BbsI": "GAAGAC",
    "EcoRI": "GAATTC",
    "BamHI": "GGATCC",
    "XhoI": "CTCGAG",
}


def normalize(seq: str) -> str:
    """Upper-case and strip whitespace from a DNA string."""
    return "".join(seq.split()).upper()


def reverse_complement(seq: str) -> str:
    return normalize(seq).translate(_COMPLEMENT)[::-1]


def gc_content(seq: str) -> float:
    seq = normalize(seq)
    if not seq:
        return 0.0
    gc = sum(1 for b in seq if b in "GC")
    return gc / len(seq)


def max_homopolymer_run(seq: str) -> int:
    """Length of the longest run of a single base."""
    seq = normalize(seq)
    best = run = 0
    prev = ""
    for b in seq:
        run = run + 1 if b == prev else 1
        prev = b
        best = max(best, run)
    return best


def self_complementarity(seq: str, min_stem: int = 3) -> int:
    """Longest internal reverse-complementary stem — a hairpin-propensity proxy.

    Returns the length of the longest substring whose reverse complement occurs
    elsewhere (non-overlapping) in the sequence. Guides with a long self-
    complementary stretch tend to fold into hairpins and load poorly.
    """
    s = normalize(seq)
    n = len(s)
    best = 0
    for i in range(n):
        for j in range(i + min_stem, n + 1):
            if j - i <= best:
                continue  # can't beat the current best from here
            rc = reverse_complement(s[i:j])
            idx = s.find(rc)
            while idx != -1:
                if idx + len(rc) <= i or idx >= j:  # non-overlapping arm
                    best = j - i
                    break
                idx = s.find(rc, idx + 1)
    return best


def contains_restriction_site(seq: str, enzyme: str) -> bool:
    """True if ``seq`` (or its reverse complement) contains the enzyme's site."""
    site = RESTRICTION_SITES.get(enzyme)
    if site is None:
        raise KeyError(f"Unknown restriction enzyme: {enzyme!r}")
    seq = normalize(seq)
    return site in seq or site in reverse_complement(seq)


def matches_iupac(seq: str, pattern: str) -> bool:
    """True if ``seq`` matches an IUPAC ``pattern`` of the same length."""
    if len(seq) != len(pattern):
        return False
    return all(b in IUPAC.get(p, "") for b, p in zip(seq.upper(), pattern.upper()))


def iter_pam_sites(
    seq: str, pam: str, spacer_length: int, pam_is_3prime: bool = True
) -> Iterator[Tuple[int, str, str]]:
    """Yield ``(spacer_start, spacer, pam_seq)`` for every PAM-flanked protospacer.

    Generalizes over enzymes: ``pam`` is an IUPAC pattern, ``spacer_length`` the
    protospacer length, and ``pam_is_3prime`` selects Cas9-style (PAM 3' of the
    spacer) vs Cas12a-style (PAM 5' of the spacer).
    """
    seq = normalize(seq)
    n = len(seq)
    plen = len(pam)
    if pam_is_3prime:
        for start in range(0, n - spacer_length - plen + 1):
            pam_seq = seq[start + spacer_length : start + spacer_length + plen]
            if matches_iupac(pam_seq, pam):
                yield start, seq[start : start + spacer_length], pam_seq
    else:
        for i in range(0, n - plen - spacer_length + 1):
            pam_seq = seq[i : i + plen]
            if matches_iupac(pam_seq, pam):
                start = i + plen
                yield start, seq[start : start + spacer_length], pam_seq


def iter_ngg_sites(seq: str, spacer_len: int = 20) -> Iterator[Tuple[int, str, str]]:
    """SpCas9 (NGG) sites — a thin wrapper over :func:`iter_pam_sites`."""
    return iter_pam_sites(seq, "NGG", spacer_len, pam_is_3prime=True)
