"""Tests for the learned outcome-model seams (BE-Hive, PRIDICT) and their
heuristic defaults. The real ML backends are exercised via fake modules (like
inDelphi); the not-installed paths raise clear errors."""

import sys
import types

import pytest

from helix.adapters.base_edit_model import (
    BEHiveBackend,
    BEHiveNotConfigured,
    HeuristicBaseEditBackend,
)
from helix.adapters.prime_edit_model import (
    HeuristicPrimeEditBackend,
    PridictBackend,
    PridictNotConfigured,
)
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5


# --- base-edit heuristic ------------------------------------------------


def test_base_edit_heuristic_peaks_at_window_centre():
    be = HeuristicBaseEditBackend()
    assert be.predict("x", "CBE", [6]).efficiency == 1.0
    assert be.predict("x", "CBE", [4]).efficiency == 0.5
    assert be.predict("x", "CBE", [6]).bystander_proportion == 0.0
    assert be.predict("x", "CBE", [4, 8]).bystander_proportion == 0.3


def test_behive_not_installed():
    with pytest.raises(BEHiveNotConfigured):
        BEHiveBackend().predict("ACGT", "CBE", [5])


def test_behive_maps_fake_model(monkeypatch):
    fake = types.ModuleType("be_predict_efficiency")
    fake.predict = lambda protospacer, editor: {"efficiency": 0.7, "bystander_proportion": 0.25}
    monkeypatch.setitem(sys.modules, "be_predict_efficiency", fake)
    pred = BEHiveBackend(celltype="HEK293").predict("ACGT", "CBE", [5, 6])
    assert pred.efficiency == 0.7 and pred.bystander_proportion == 0.25
    assert pred.predictor == "behive:HEK293"


# --- prime-edit heuristic -----------------------------------------------


def test_prime_edit_heuristic_in_range_and_prefers_balanced_pbs():
    pe = HeuristicPrimeEditBackend()
    balanced = pe.predict("s", "ACGTACGTACGTA", "rtt", "A>G @ 1").efficiency  # 13 nt, ~50% GC
    skewed = pe.predict("s", "AAAAAAAAAAAAA", "rtt", "A>G @ 1").efficiency  # 0% GC
    assert 0.0 <= skewed < balanced <= 1.0


def test_pridict_not_installed():
    with pytest.raises(PridictNotConfigured):
        PridictBackend().predict("s", "pbs", "rtt", "A>G @ 1")


def test_pridict_maps_fake_model(monkeypatch):
    fake = types.ModuleType("pridict")
    fake.predict = lambda spacer, pbs, rtt: {"efficiency": 0.55}
    monkeypatch.setitem(sys.modules, "pridict", fake)
    assert PridictBackend().predict("s", "pbs", "rtt", "A>G @ 1").efficiency == 0.55


# --- pipeline wiring ----------------------------------------------------


def test_base_edit_pipeline_stamps_model():
    spec = parse_spec({"name": "be", "target": {"gene": "X", "sequence": SEQ},
                       "strategy": {"modality": "base_edit", "editor": "CBE"},
                       "constraints": {"on_target_min_efficiency": 0.0},
                       "simulate": {"on_target": "heuristic_gc"}})
    design = compile_spec(spec)
    g = design.guides[0]
    assert g.base_edit.predictor == "window_heuristic"
    assert g.base_edit.efficiency > 0
    assert design.provenance.adapters.get("base_edit_model") == "window_heuristic"


def test_prime_edit_pipeline_populates_efficiency():
    assert SEQ[25] == "G"
    spec = parse_spec({"name": "pe", "target": {"gene": "X", "sequence": SEQ, "edit": "G>A @ 26"},
                       "strategy": {"modality": "prime_edit"},
                       "constraints": {"on_target_min_efficiency": 0.0, "guides_count": 1},
                       "simulate": {"on_target": "heuristic_gc"}})
    design = compile_spec(spec)
    p = design.prime_edits[0]
    assert p.predicted_efficiency > 0 and p.predictor == "pe_heuristic"


def test_requesting_uninstalled_behive_errors_at_compile():
    spec = parse_spec({"name": "be", "target": {"gene": "X", "sequence": SEQ},
                       "strategy": {"modality": "base_edit", "editor": "CBE"},
                       "constraints": {"on_target_min_efficiency": 0.0},
                       "simulate": {"on_target": "heuristic_gc", "base_edit_model": "behive"}})
    with pytest.raises(BEHiveNotConfigured):
        compile_spec(spec)
