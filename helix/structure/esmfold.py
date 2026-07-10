"""Real protein folding via the public ESMFold API (no key, no GPU needed).

ESMFold predicts a single protein chain's 3D structure and returns a PDB whose
B-factor column carries per-residue pLDDT confidence. It is protein-only and caps
at a few hundred residues, so it folds a *domain* of SpCas9 here — a genuine,
runnable structure prediction. The full Cas9-gRNA-DNA complex still needs
AlphaFold3/Boltz (GPU) behind the ``StructureBackend`` seam.
"""

from __future__ import annotations

import urllib.request

_ESMFOLD_URL = "https://api.esmatlas.com/foldSequence/v1/pdb/"
_MAX_RESIDUES = 400  # public API limit


class EsmFoldError(RuntimeError):
    pass


def esmfold_pdb(sequence: str, timeout: int = 90) -> str:
    """Fold a protein sequence with ESMFold; return the PDB text."""
    seq = "".join(c for c in sequence.upper() if c.isalpha())
    if not seq:
        raise EsmFoldError("empty sequence")
    if len(seq) > _MAX_RESIDUES:
        raise EsmFoldError(f"ESMFold caps at ~{_MAX_RESIDUES} residues; got {len(seq)}.")
    req = urllib.request.Request(_ESMFOLD_URL, data=seq.encode())
    try:
        pdb = urllib.request.urlopen(req, timeout=timeout).read().decode()
    except Exception as exc:  # network / service error
        raise EsmFoldError(f"ESMFold request failed: {exc}")
    if "ATOM" not in pdb:
        raise EsmFoldError("ESMFold returned no structure")
    return pdb


def mean_plddt(pdb: str) -> float:
    """Mean CA pLDDT (0–100) from a PDB (ESMFold writes pLDDT into the B-factor
    column; the esmatlas API uses a 0–1 scale, normalized here to conventional 0–100)."""
    vals = []
    for line in pdb.splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            try:
                vals.append(float(line[60:66]))
            except ValueError:
                pass
    if not vals:
        return 0.0
    m = sum(vals) / len(vals)
    return round(m * 100 if m <= 1.5 else m, 1)


# SpCas9 (UniProt Q99ZW2) functional domains — (0-based start, end, label).
SPCAS9_DOMAINS = {
    "hnh": (775, 908, "HNH nuclease domain"),
    "pi": (1099, 1368, "PAM-interacting domain"),
    "bridge": (54, 94, "bridge helix"),
}
