"""Prime-editing efficiency models.

* ``HeuristicPrimeEditBackend`` (offline default) — a transparent estimate from
  PBS composition/length (PBS binding strength is a known efficiency determinant).
* ``PridictBackend`` — the learned PRIDICT model (Mathis et al., Nat Biotechnol
  2021), wired injectably like inDelphi/BE-Hive.

Reference: Mathis et al., "Predicting prime editing efficiency and product purity
by deep learning", Nature Biotechnology 41, 1151-1159 (2023).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helix.bio import gc_content


@dataclass
class PrimeEditPrediction:
    efficiency: float  # 0..1
    predictor: str


@runtime_checkable
class PrimeEditBackend(Protocol):
    def predict(self, spacer: str, pbs: str, rtt: str, edit: str) -> PrimeEditPrediction:
        ...


class HeuristicPrimeEditBackend:
    name = "pe_heuristic"

    def predict(self, spacer: str, pbs: str, rtt: str, edit: str) -> PrimeEditPrediction:
        # PBS binds the nicked 3' end; moderate GC (~50%) and length ~13 bind best.
        gc_term = max(0.0, 1.0 - abs(gc_content(pbs) - 0.5) / 0.5)
        len_term = max(0.0, 1.0 - abs(len(pbs) - 13) / 13.0)
        efficiency = 0.15 + 0.6 * gc_term * (0.5 + 0.5 * len_term)
        return PrimeEditPrediction(round(min(1.0, efficiency), 3), self.name)


class PridictNotConfigured(RuntimeError):
    pass


class PridictBackend:
    """Learned PRIDICT model. Injectable, lazy import, clear error if absent."""

    name = "pridict"

    def __init__(self):
        self._model = None

    def _ensure(self):
        try:
            import pridict  # heavy, optional
        except ImportError as exc:
            raise PridictNotConfigured(
                "PRIDICT is not installed. Install it or use 'pe_heuristic'."
            ) from exc
        if self._model is None:
            self._model = pridict
        return self._model

    def predict(self, spacer: str, pbs: str, rtt: str, edit: str) -> PrimeEditPrediction:
        model = self._ensure()
        result = model.predict(spacer=spacer, pbs=pbs, rtt=rtt)  # version-specific call
        return PrimeEditPrediction(float(result.get("efficiency", 0.0)), self.name)
