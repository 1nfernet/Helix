"""Tests for the Ensembl sequence provider.

Unit tests inject a fake HTTP client so they run fully offline and
deterministically. A live integration test is gated behind an env var so it never
flakes CI but can be run on demand:  HELIX_ENSEMBL_IT=1 pytest -k integration
"""

import os

import pytest

from helix.adapters.ensembl import EnsemblError, EnsemblSequenceProvider
from helix.adapters.registry import default_registry
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec

# A canned TP53 lookup + a 300 nt window, keyed by URL fragment.
_LOOKUP = {
    "seq_region_name": "17",
    "start": 7661779,
    "end": 7687546,
    "strand": -1,
    "assembly_name": "GRCh38",
}
_SEQ = "ACGTACGTGG" * 30  # 300 nt, contains NGG sites


def _fake_get_json(url: str):
    if "/lookup/symbol/" in url:
        return dict(_LOOKUP)
    if "/sequence/region/" in url:
        assert "17:7661779-7662078:-1" in url  # window math is correct
        return {"seq": _SEQ, "molecule": "dna"}
    raise AssertionError(f"unexpected URL: {url}")


def _spec(**over):
    data = {
        "name": "ens",
        "target": {"gene": "TP53"},
        "simulate": {"sequence_provider": "ensembl"},
    }
    data.update(over)
    return parse_spec(data)


def test_resolve_fetches_bounded_window():
    provider = EnsemblSequenceProvider(window_length=300, get_json=_fake_get_json)
    target = provider.resolve(_spec())
    assert target.gene == "TP53"
    assert target.length == 300
    assert target.sequence == _SEQ
    assert "17:7661779-7662078:-1" in target.source


def test_rejects_non_grch38_build():
    provider = EnsemblSequenceProvider(get_json=_fake_get_json)
    with pytest.raises(EnsemblError):
        provider.resolve(_spec(genome_build="GRCh37"))


def test_pipeline_runs_end_to_end_with_ensembl_seam():
    # Prove the adapter drops into the compiler via the registry, offline.
    reg = default_registry()
    reg.register_sequence(EnsemblSequenceProvider(get_json=_fake_get_json))
    design = compile_spec(_spec(), registry=reg)
    assert design.target is not None
    assert design.target.source.startswith("ensembl@")
    assert design.guides, "expected guides from the Ensembl-provided window"


@pytest.mark.skipif(
    os.environ.get("HELIX_ENSEMBL_IT") != "1",
    reason="live network test; set HELIX_ENSEMBL_IT=1 to run",
)
def test_integration_live_ensembl():
    provider = EnsemblSequenceProvider(window_length=120)
    target = provider.resolve(_spec())
    assert target.length == 120
    assert set(target.sequence) <= set("ACGTN")
