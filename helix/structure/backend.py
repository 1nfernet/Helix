"""Injectable structure-prediction backend (AlphaFold3 / Boltz).

The predictor is a heavy GPU tool, so it sits behind an injectable ``run``: the
default shells out and parses the confidence output; tests inject a fake. A
missing binary raises ``StructureNotConfigured`` with guidance.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Callable, Dict, Protocol, runtime_checkable

RunFn = Callable[[str, dict, str], Dict]  # (binary, complex_json, outdir) -> confidence dict


@runtime_checkable
class StructureBackend(Protocol):
    name: str

    def fold(self, complex_json: dict) -> Dict:
        ...


class StructureError(RuntimeError):
    pass


class StructureNotConfigured(StructureError):
    """Raised when the folding binary is unavailable."""


def _default_run(binary: str, complex_json: dict, outdir: str) -> Dict:
    import subprocess

    inp = os.path.join(outdir, "input.json")
    with open(inp, "w") as fh:
        json.dump(complex_json, fh)
    try:
        proc = subprocess.run([binary, inp, "--out_dir", outdir], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise StructureNotConfigured(
            f"folding binary {binary!r} not found. Install AlphaFold3/Boltz or set "
            "HELIX_FOLDING_BIN."
        ) from exc
    if proc.returncode != 0:
        raise StructureError(f"folding tool failed: {proc.stderr.strip()}")

    matches = glob.glob(os.path.join(outdir, "**", "*confidence*.json"), recursive=True)
    if not matches:
        raise StructureError("folding tool produced no confidence output")
    with open(matches[0]) as fh:
        data = json.load(fh)
    return {
        "ptm": data.get("ptm", 0.0),
        "iptm": data.get("iptm", 0.0),
        "plddt": data.get("plddt", data.get("mean_plddt", 0.0)),
        "structure_path": _first_structure(outdir),
    }


def _first_structure(outdir: str):
    for pattern in ("**/*.cif", "**/*.pdb"):
        hits = glob.glob(os.path.join(outdir, pattern), recursive=True)
        if hits:
            return hits[0]
    return None


class SubprocessFoldingBackend:
    def __init__(self, tool: str = "boltz", binary: str = None, run: RunFn = _default_run):
        self.name = tool
        self.binary = binary or tool
        self._run = run

    @classmethod
    def from_env(cls) -> "SubprocessFoldingBackend":
        return cls(
            tool=os.environ.get("HELIX_FOLDING_TOOL", "boltz"),
            binary=os.environ.get("HELIX_FOLDING_BIN"),
        )

    def fold(self, complex_json: dict) -> Dict:
        import tempfile

        with tempfile.TemporaryDirectory() as outdir:
            return self._run(self.binary, complex_json, outdir)
