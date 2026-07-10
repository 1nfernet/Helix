"""CRISPResso2 analysis adapter.

Pure parsers for CRISPResso2's output files (verified against the tool's source
format), plus an injectable subprocess backend so the integration is unit-tested
offline and configured in only when CRISPResso2 is installed.
"""

from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass
from typing import Callable, Optional, Protocol, runtime_checkable

from helix.analysis.models import EditingAnalysis

_RUN_NAME = "helix"


# --- pure parsers -------------------------------------------------------


def parse_quantification(text: str) -> dict:
    """Parse ``CRISPResso_quantification_of_editing_frequency.txt`` (first amplicon row)."""
    rows = [ln for ln in text.splitlines() if ln.strip()]
    if len(rows) < 2:
        raise ValueError("empty CRISPResso quantification table")
    header = rows[0].split("\t")
    values = rows[1].split("\t")
    d = dict(zip(header, values))

    def num(key, cast=int):
        return cast(d[key]) if key in d and d[key] != "" else cast(0)

    return {
        "editing_efficiency": float(d["Modified%"]) / 100.0,
        "reads_aligned": num("Reads_aligned"),
        "modified_reads": num("Modified"),
        "unmodified_reads": num("Unmodified"),
        "insertions": num("Insertions"),
        "deletions": num("Deletions"),
        "substitutions": num("Substitutions"),
    }


def parse_frameshift_analysis(text: str) -> dict:
    """Parse ``*Frameshift_analysis.txt``: noncoding / in-frame / frameshift read counts."""
    def grab(label):
        m = re.search(rf"{label} mutation:(\d+)\s*reads", text)
        return int(m.group(1)) if m else 0

    noncoding = grab("Noncoding")
    in_frame = grab("In-frame")
    frameshift = grab("Frameshift")
    coding = in_frame + frameshift
    return {
        "noncoding": noncoding,
        "in_frame": in_frame,
        "frameshift": frameshift,
        # Frameshift among coding edits — comparable to inDelphi's frameshift fraction.
        "frameshift_fraction": (frameshift / coding) if coding > 0 else None,
    }


# --- injectable backend -------------------------------------------------


@dataclass
class RawCrispresso:
    quantification: str
    frameshift: Optional[str] = None


@runtime_checkable
class AnalysisBackend(Protocol):
    def run(self, amplicon: str, reads: str, coding_seq: Optional[str]) -> RawCrispresso:
        ...


class Crispresso2Error(RuntimeError):
    pass


class Crispresso2NotConfigured(Crispresso2Error):
    """Raised when the CRISPResso binary is not available."""


# execute(binary, args, out_base) -> None; populates out_base with CRISPResso output files.
ExecFn = Callable[[str, list, str], None]


def _default_execute(binary: str, args: list, out_base: str) -> None:
    import subprocess

    try:
        proc = subprocess.run([binary, *args], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise Crispresso2NotConfigured(
            f"CRISPResso binary {binary!r} not found. Install CRISPResso2 or set "
            "HELIX_CRISPRESSO_BIN."
        ) from exc
    if proc.returncode != 0:
        raise Crispresso2Error(f"CRISPResso failed: {proc.stderr.strip()}")


def _read(path: str) -> Optional[str]:
    return open(path).read() if os.path.exists(path) else None


class Crispresso2Backend:
    """Runs the CRISPResso2 CLI and returns its raw output files."""

    def __init__(self, binary: str = "CRISPResso", execute: ExecFn = _default_execute):
        self.binary = binary
        self._execute = execute

    @classmethod
    def from_env(cls) -> "Crispresso2Backend":
        return cls(binary=os.environ.get("HELIX_CRISPRESSO_BIN", "CRISPResso"))

    def run(self, amplicon: str, reads: str, coding_seq: Optional[str] = None) -> RawCrispresso:
        import tempfile

        with tempfile.TemporaryDirectory() as outdir:
            args = [
                "--amplicon_seq", amplicon,
                "--fastq_r1", reads,
                "-o", outdir,
                "-n", _RUN_NAME,
            ]
            if coding_seq:
                args += ["--coding_seq", coding_seq]
            base = os.path.join(outdir, f"CRISPResso_on_{_RUN_NAME}")
            os.makedirs(base, exist_ok=True)
            self._execute(self.binary, args, base)

            quant = _read(os.path.join(base, "CRISPResso_quantification_of_editing_frequency.txt"))
            if quant is None:
                raise Crispresso2Error("CRISPResso produced no quantification table")
            fs_files = glob.glob(os.path.join(base, "*Frameshift_analysis.txt"))
            frameshift = _read(fs_files[0]) if fs_files else None
            return RawCrispresso(quantification=quant, frameshift=frameshift)


class CrispressoAnalyzer:
    """Turns CRISPResso2 output into a normalized ``EditingAnalysis``."""

    name = "crispresso2"

    def __init__(self, backend: AnalysisBackend):
        self._backend = backend

    def analyze(
        self, amplicon: str, reads: str, coding_seq: Optional[str] = None
    ) -> EditingAnalysis:
        raw = self._backend.run(amplicon, reads, coding_seq)
        q = parse_quantification(raw.quantification)
        frameshift_fraction = None
        if raw.frameshift:
            frameshift_fraction = parse_frameshift_analysis(raw.frameshift)["frameshift_fraction"]
        return EditingAnalysis(
            editing_efficiency=q["editing_efficiency"],
            reads_aligned=q["reads_aligned"],
            modified_reads=q["modified_reads"],
            unmodified_reads=q["unmodified_reads"],
            insertions=q["insertions"],
            deletions=q["deletions"],
            substitutions=q["substitutions"],
            frameshift_fraction=frameshift_fraction,
            analyzer=f"{self.name}",
        )
