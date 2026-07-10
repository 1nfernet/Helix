"""Tests for the inDelphi repair-outcome adapter.

inDelphi is a trained ML model, so (unlike Doench/CFD) we can't reproduce its
numbers offline. We instead test what Helix owns: the output→IR mapping, the
backend's dataframe/stats conversion (via a fake ``inDelphi`` module), the
not-installed error path, and the compiler seam.
"""

import sys
import types

import pytest

from helix.adapters.base import ScorerContextError
from helix.adapters.repair import (
    InDelphiBackend,
    InDelphiNotConfigured,
    InDelphiRepairPredictor,
    RepairGenotype,
    RepairPrediction,
)
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec

SEQ = "ACGT" * 20


class _FakeBackend:
    def __init__(self, prediction):
        self._p = prediction

    def predict(self, sequence, cutsite):
        return self._p


def test_mapping_to_repair_outcome():
    pred = RepairPrediction(
        frameshift_fraction=0.73,
        genotypes=[
            RepairGenotype("del", 3, 0.4, "3bp_deletion"),
            RepairGenotype("ins", 1, 0.2, "1bp_insertion"),
        ],
    )
    out = InDelphiRepairPredictor(_FakeBackend(pred), celltype="HEK293").predict(SEQ, 40)
    assert out.frameshift_fraction == 0.73
    assert out.top_outcomes == [{"3bp_deletion": 0.4}, {"1bp_insertion": 0.2}]
    assert out.predictor == "indelphi@HEK293"


def test_backend_not_installed_raises_configured_error():
    # inDelphi is not installed in this environment.
    with pytest.raises(InDelphiNotConfigured):
        InDelphiBackend(celltype="mESC").predict(SEQ, 40)


def test_invalid_celltype_rejected():
    with pytest.raises(ValueError):
        InDelphiBackend(celltype="bogus")


# --- exercise the real backend's pandas-facing conversion with a fake module --


class _FakeDF:
    """Minimal stand-in for the pandas frame inDelphi returns."""

    def __init__(self, rows):
        self._rows = rows

    def sort_values(self, col, ascending=True):
        return _FakeDF(sorted(self._rows, key=lambda r: r[col], reverse=not ascending))

    def head(self, n):
        return _FakeDF(self._rows[:n])

    def iterrows(self):
        return enumerate(self._rows)


def _install_fake_indelphi(monkeypatch, predict_impl):
    fake = types.ModuleType("inDelphi")
    fake.init_model = lambda **kw: None
    fake.predict = predict_impl
    monkeypatch.setitem(sys.modules, "inDelphi", fake)


def test_backend_converts_df_and_stats(monkeypatch):
    rows = [
        {"Category": "del", "Length": 3, "Predicted frequency": 40.0},
        {"Category": "ins", "Length": 1, "Predicted frequency": 20.0},
    ]
    _install_fake_indelphi(
        monkeypatch, lambda seq, cut: (_FakeDF(rows), {"Frameshift frequency": 77.0})
    )
    pred = InDelphiBackend(celltype="mESC").predict(SEQ, 40)
    assert pred.frameshift_fraction == pytest.approx(0.77)
    assert pred.genotypes[0].label == "3bp_deletion"  # sorted desc by frequency
    assert pred.genotypes[1].label == "1bp_insertion"


def test_backend_error_result_becomes_context_error(monkeypatch):
    _install_fake_indelphi(monkeypatch, lambda seq, cut: "error: cutsite too close to edge")
    with pytest.raises(ScorerContextError):
        InDelphiBackend(celltype="mESC").predict(SEQ, 2)


def test_pipeline_uses_indelphi_seam():
    pred = RepairPrediction(0.66, [RepairGenotype("del", 2, 0.5, "2bp_deletion")])
    reg_spec = parse_spec(
        {
            "name": "rep",
            "target": {"gene": "TP53", "sequence": "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4},
            "simulate": {"repair_outcome": "indelphi"},
        }
    )
    from helix.adapters.registry import default_registry

    reg = default_registry()
    reg.register_repair(InDelphiRepairPredictor(_FakeBackend(pred)))
    design = compile_spec(reg_spec, registry=reg)
    assert design.guides
    assert all(g.repair.predictor.startswith("indelphi@") for g in design.guides)
    assert all(g.repair.frameshift_fraction == 0.66 for g in design.guides)
