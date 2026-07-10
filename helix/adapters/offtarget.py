"""Off-target scoring: Cas-OFFinder (genome scan) + CFD (cut-likelihood score).

Two concerns, cleanly separated:

* **CFD** (:func:`cfd_score`) is a pure, published computation (Doench 2016). It
  scores how likely a given off-target site is to be cut, from the position and
  identity of each mismatch plus the PAM. Tables live in
  :mod:`helix.adapters.data.cfd2016`; the routine here is an independent
  re-implementation cross-checked against the reference calculator.

* **Cas-OFFinder** supplies the candidate sites — the heavy part, a genome-wide
  scan by an external binary. It sits behind an injectable
  :class:`OffTargetSiteFinder`, so the scorer is unit-testable offline (fake
  finder) and degrades with a clear, actionable error when the binary/genome are
  not configured. This mirrors the Ensembl adapter's injectable-transport design.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, runtime_checkable

from helix.adapters.data import cfd2016
from helix.bio import normalize
from helix.ir.design import OffTargetReport, OffTargetSite

# Complement used by CFD (matches the reference: T and U both complement to A).
_COMPLEMENT = {"A": "T", "C": "G", "G": "C", "T": "A", "U": "A"}


def cfd_score(guide: str, offtarget: str) -> float:
    """CFD score in [0, 1] for a guide vs. a candidate off-target site.

    ``guide`` is the intended protospacer (e.g. 20 nt). ``offtarget`` is the
    matched genomic site including PAM (protospacer + >= 2 nt PAM); the last 2 nt
    are read as the PAM dinucleotide. An identical site with a GG PAM scores 1.0.
    """
    guide = normalize(guide)
    site = normalize(offtarget)
    n = len(guide)
    if len(site) < n + 2:
        raise ValueError(f"off-target {site!r} too short for a {n} nt guide + PAM")

    proto = site[:n]
    pam = site[-2:]

    score = 1.0
    g = guide.replace("T", "U")
    s = proto.replace("T", "U")
    for i, sbase in enumerate(s):
        if g[i] == sbase:
            continue
        key = f"r{g[i]}:d{_COMPLEMENT.get(sbase, 'A')},{i + 1}"
        # Unknown mismatch key (non-ACGT base) -> no penalty: conservative for a
        # safety metric (assume it could still cut).
        score *= cfd2016.MISMATCH_SCORES.get(key, 1.0)
    # Invalid/non-ACGT PAM -> 0.0 (not a real NGG target).
    score *= cfd2016.PAM_SCORES.get(pam, 0.0)
    return score


# --- candidate site discovery ------------------------------------------


@dataclass
class OffTargetHit:
    chrom: str
    position: int
    strand: str
    dna: str  # matched site including PAM, uppercase
    mismatches: int


@runtime_checkable
class OffTargetSiteFinder(Protocol):
    def find(self, spacer: str, genome_build: str) -> List[OffTargetHit]:
        ...


class CasOffinderError(RuntimeError):
    pass


class CasOffinderNotConfigured(CasOffinderError):
    """Raised when the binary/genome needed for a real scan are not configured."""


def build_casoffinder_input(
    spacer: str, genome_path: str, pam: str = "NGG", max_mismatches: int = 4
) -> str:
    """Render a Cas-OFFinder input file (pure)."""
    pattern = "N" * len(spacer) + pam
    query = spacer + "N" * len(pam)
    return f"{genome_path}\n{pattern}\n{query} {max_mismatches}\n"


def parse_casoffinder_output(text: str) -> List[OffTargetHit]:
    """Parse Cas-OFFinder output (pure). Handles the bulge and non-bulge layouts."""
    hits: List[OffTargetHit] = []
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) < 6:
            f = line.split()
        if len(f) < 6:
            continue
        if f[0] in ("X", "DNA", "RNA"):  # bulge layout: type,crRNA,DNA,chrom,pos,dir,mm,[bulge]
            _, _crrna, dna, chrom, pos, direction, mm = f[0], f[1], f[2], f[3], f[4], f[5], f[6]
        else:  # non-bulge: crRNA,chrom,pos,DNA,dir,mm
            _crrna, chrom, pos, dna, direction, mm = f[0], f[1], f[2], f[3], f[4], f[5]
        hits.append(
            OffTargetHit(
                chrom=chrom,
                position=int(pos),
                strand=direction,
                dna=dna.upper(),
                mismatches=int(mm),
            )
        )
    return hits


RunFn = Callable[[str, str, str], str]  # (binary, device, input_text) -> stdout text


def _default_run(binary: str, device: str, input_text: str) -> str:
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "in.txt")
        outp = os.path.join(d, "out.txt")
        with open(inp, "w") as fh:
            fh.write(input_text)
        try:
            proc = subprocess.run(
                [binary, inp, device, outp], capture_output=True, text=True
            )
        except FileNotFoundError as exc:
            raise CasOffinderNotConfigured(
                f"cas-offinder binary {binary!r} not found. Install it and/or set "
                "HELIX_CASOFFINDER_BIN."
            ) from exc
        if proc.returncode != 0:
            raise CasOffinderError(f"cas-offinder failed: {proc.stderr.strip()}")
        with open(outp) as fh:
            return fh.read()


class CasOffinderRunner:
    """Finds candidate off-targets by shelling out to Cas-OFFinder."""

    def __init__(
        self,
        genome_path: Optional[str] = None,
        binary: str = "cas-offinder",
        device: str = "C",
        pam: str = "NGG",
        max_mismatches: int = 4,
        run: RunFn = _default_run,
    ):
        self.genome_path = genome_path
        self.binary = binary
        self.device = device
        self.pam = pam
        self.max_mismatches = max_mismatches
        self._run = run

    @classmethod
    def from_env(cls) -> "CasOffinderRunner":
        return cls(
            genome_path=os.environ.get("HELIX_GENOME_DIR"),
            binary=os.environ.get("HELIX_CASOFFINDER_BIN", "cas-offinder"),
            device=os.environ.get("HELIX_CASOFFINDER_DEVICE", "C"),
        )

    def find(self, spacer: str, genome_build: str) -> List[OffTargetHit]:
        if not self.genome_path:
            raise CasOffinderNotConfigured(
                "Real off-target scanning needs a genome. Set HELIX_GENOME_DIR to a "
                "Cas-OFFinder genome (dir/2bit/fasta), or use the 'mock_seed' scorer."
            )
        text = self._run(
            self.binary,
            self.device,
            build_casoffinder_input(spacer, self.genome_path, self.pam, self.max_mismatches),
        )
        return parse_casoffinder_output(text)


# --- the OffTargetScorer -----------------------------------------------


class CasOffinderCfdScorer:
    """OffTargetScorer: Cas-OFFinder candidate sites scored by CFD."""

    name = "cas_offinder_cfd"
    version = "doench2016"

    def __init__(self, finder: OffTargetSiteFinder, max_sites: int = 20):
        self._finder = finder
        self.max_sites = max_sites

    def scan(self, spacer: str, genome_build: str) -> OffTargetReport:
        spacer = normalize(spacer)
        hits = self._finder.find(spacer, genome_build)

        # The intended on-target is one perfect (0-mismatch) hit; drop exactly one.
        # Any *additional* perfect matches are genuine (identical) off-targets.
        perfect = [h for h in hits if h.mismatches == 0]
        offs = [h for h in hits if h.mismatches > 0] + perfect[1:]

        scored: List[OffTargetSite] = []
        worst = 0.0
        for h in offs:
            if len(h.dna) < len(spacer) + 2:
                continue  # bulge/indel site; CFD is defined for substitutions only
            cfd = cfd_score(spacer, h.dna)
            worst = max(worst, cfd)
            scored.append(
                OffTargetSite(
                    sequence=h.dna,
                    mismatches=h.mismatches,
                    cfd=round(cfd, 4),
                    locus=f"{h.chrom}:{h.position}:{h.strand}",
                )
            )

        scored.sort(key=lambda s: -s.cfd)
        return OffTargetReport(
            max_cfd=round(worst, 4),
            site_count=len(scored),
            sites=scored[: self.max_sites],
            scorer=f"{self.name}@{self.version}",
        )
