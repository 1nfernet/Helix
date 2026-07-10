"""Base-editing outcome models.

The *window analysis* (which bases are editable, bystanders) is exact and lives in
the designer. The *efficiency and bystander proportion* come from a model behind
this seam:

* ``HeuristicBaseEditBackend`` (offline default) — a transparent positional
  heuristic (editing peaks at window centre; more editable bases -> more bystanders).
* ``BEHiveBackend`` — the learned BE-Hive model (Arbab et al., Cell 2020), a heavy
  ML pipeline wired like inDelphi: injectable, lazy import, clear error if absent.

Reference: Arbab et al., "Determinants of Base Editing Outcomes from Target Library
Analysis and Machine Learning", Cell 182, 463-480 (2020).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, runtime_checkable

_WINDOW_CENTRE = 6.0


@dataclass
class BaseEditPrediction:
    efficiency: float  # 0..1
    bystander_proportion: float  # 0..1
    predictor: str


@runtime_checkable
class BaseEditBackend(Protocol):
    def predict(self, protospacer: str, editor: str, edited_positions: List[int]) -> BaseEditPrediction:
        ...


class HeuristicBaseEditBackend:
    name = "window_heuristic"

    def predict(self, protospacer: str, editor: str, edited_positions: List[int]) -> BaseEditPrediction:
        if not edited_positions:
            return BaseEditPrediction(0.0, 0.0, self.name)
        best = min(edited_positions, key=lambda p: abs(p - _WINDOW_CENTRE))
        efficiency = max(0.2, 1.0 - abs(best - _WINDOW_CENTRE) / 4.0)
        # More editable bases in the window -> higher chance of bystander edits.
        bystander_proportion = min(1.0, 0.3 * (len(edited_positions) - 1))
        return BaseEditPrediction(round(efficiency, 3), round(bystander_proportion, 3), self.name)


class BEHiveNotConfigured(RuntimeError):
    pass


class BEHiveBackend:
    """Learned BE-Hive model. Wired like inDelphi: injectable, lazy, clear error."""

    name = "behive"

    def __init__(self, celltype: str = "mES"):
        self.celltype = celltype
        self._model = None

    def _ensure(self):
        try:
            import be_predict_efficiency  # heavy, optional
        except ImportError as exc:
            raise BEHiveNotConfigured(
                "BE-Hive is not installed (be_predict_efficiency / be_predict_bystander). "
                "Install it or use 'window_heuristic'."
            ) from exc
        if self._model is None:
            self._model = be_predict_efficiency
        return self._model

    def predict(self, protospacer: str, editor: str, edited_positions: List[int]) -> BaseEditPrediction:
        model = self._ensure()
        # BE-Hive returns per-edit predictions; we normalize to an overall efficiency
        # and a bystander proportion. (The exact call is version-specific.)
        result = model.predict(protospacer, editor)
        efficiency = float(result.get("efficiency", 0.0))
        bystander = float(result.get("bystander_proportion", 0.0))
        return BaseEditPrediction(efficiency, bystander, f"{self.name}:{self.celltype}")
