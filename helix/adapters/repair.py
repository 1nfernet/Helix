"""Repair-outcome prediction: inDelphi.

Unlike the on-target (Doench 2014) and off-target CFD (Doench 2016) models —
small published coefficient tables we reimplement and verify exactly — inDelphi
is a *trained ML pipeline* (per-cell-type pickled sklearn/NN models). So it is
wired like Cas-OFFinder: the heavy model sits behind an injectable
:class:`RepairBackend`, the output→IR mapping is pure tested code, and a missing
install fails with a clear, actionable error.

* ``InDelphiBackend`` calls the real ``inDelphi`` package (lazy import; per-cell-type).
* ``InDelphiRepairPredictor`` maps its normalized output onto ``RepairOutcome``.
* Tests inject a fake backend, so the mapping and the compiler seam are covered
  offline without pandas/scipy/sklearn or the model files.

Reference: Shen, Arbab, Hsu, et al., "Predictable and precise template-free
CRISPR editing of pathogenic variants", Nature 563, 646-651 (2018).
Model/package: https://github.com/maxwshen/inDelphi-model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Protocol, runtime_checkable

from helix.adapters.base import ScorerContextError
from helix.bio import normalize
from helix.ir.design import RepairOutcome

_CELLTYPES = {"mESC", "U2OS", "HEK293", "HCT116", "K562"}
_TOP_N = 6  # how many top genotypes to surface in the report


@dataclass
class RepairGenotype:
    category: str  # 'del' | 'ins'
    length: int
    frequency: float  # 0..1
    label: str


@dataclass
class RepairPrediction:
    """Backend-neutral normalization of a repair-outcome prediction."""

    frameshift_fraction: float  # 0..1
    genotypes: List[RepairGenotype] = field(default_factory=list)


@runtime_checkable
class RepairBackend(Protocol):
    def predict(self, sequence: str, cutsite: int) -> RepairPrediction:
        ...


class InDelphiNotConfigured(RuntimeError):
    """Raised when the inDelphi package/model is not importable."""


class InDelphiBackend:
    """Real backend: drives the ``inDelphi`` package for one cell type."""

    def __init__(self, celltype: str = "mESC"):
        if celltype not in _CELLTYPES:
            raise ValueError(f"inDelphi celltype must be one of {sorted(_CELLTYPES)}")
        self.celltype = celltype
        self._model = None

    def _ensure_model(self):
        try:
            import inDelphi  # heavy, optional dependency
        except ImportError as exc:
            raise InDelphiNotConfigured(
                "inDelphi is not installed. Install it (see "
                "github.com/maxwshen/inDelphi-model) or use the 'mock_indel' predictor."
            ) from exc
        if self._model is None:
            inDelphi.init_model(celltype=self.celltype)
            self._model = inDelphi
        return self._model

    def predict(self, sequence: str, cutsite: int) -> RepairPrediction:
        model = self._ensure_model()
        result = model.predict(sequence, cutsite)
        # inDelphi returns (pred_df, stats) on success, or an error otherwise.
        if not isinstance(result, tuple) or len(result) != 2:
            raise ScorerContextError(
                f"inDelphi could not predict at cutsite {cutsite} (context too short?)"
            )
        pred_df, stats = result
        frameshift = float(stats["Frameshift frequency"]) / 100.0

        top = pred_df.sort_values("Predicted frequency", ascending=False).head(_TOP_N)
        genotypes = []
        for _, row in top.iterrows():
            category = str(row["Category"])
            length = int(row["Length"])
            freq = float(row["Predicted frequency"]) / 100.0
            kind = "insertion" if category == "ins" else "deletion"
            genotypes.append(
                RepairGenotype(category=category, length=length, frequency=freq,
                               label=f"{length}bp_{kind}")
            )
        return RepairPrediction(frameshift_fraction=frameshift, genotypes=genotypes)


class InDelphiRepairPredictor:
    """RepairOutcomePredictor backed by inDelphi (or an injected fake in tests)."""

    name = "indelphi"

    def __init__(self, backend: RepairBackend, celltype: str = "mESC"):
        self._backend = backend
        self.version = celltype

    def predict(self, sequence: str, cutsite: int) -> RepairOutcome:
        prediction = self._backend.predict(normalize(sequence), cutsite)
        fs = min(1.0, max(0.0, prediction.frameshift_fraction))
        top_outcomes = [{g.label: round(g.frequency, 4)} for g in prediction.genotypes]
        return RepairOutcome(
            frameshift_fraction=round(fs, 4),
            top_outcomes=top_outcomes,
            predictor=f"{self.name}@{self.version}",
        )
