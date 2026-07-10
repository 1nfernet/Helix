"""Adapter registry — maps DSL string keys to adapter instances.

The ``simulate`` block of a spec names adapters by key (e.g.
``on_target: heuristic_gc``). The registry resolves those keys, so choosing a
different tool is a spec edit, not a code change. Real tool wrappers register
themselves here (or via entry points) without the compiler knowing they exist.
"""

from __future__ import annotations

from typing import Dict

from helix.adapters import base, builtins
from helix.adapters.base_edit_model import BEHiveBackend, HeuristicBaseEditBackend
from helix.adapters.ensembl import EnsemblSequenceProvider
from helix.adapters.ncbi import FallbackSequenceProvider, NcbiSequenceProvider
from helix.adapters.offtarget import CasOffinderCfdScorer, CasOffinderRunner
from helix.adapters.ontarget import RuleSet1OnTargetScorer
from helix.adapters.prime_edit_model import HeuristicPrimeEditBackend, PridictBackend
from helix.adapters.repair import InDelphiBackend, InDelphiRepairPredictor


class AdapterRegistry:
    def __init__(self) -> None:
        self._sequence: Dict[str, base.SequenceProvider] = {}
        self._on_target: Dict[str, base.OnTargetScorer] = {}
        self._off_target: Dict[str, base.OffTargetScorer] = {}
        self._repair: Dict[str, base.RepairOutcomePredictor] = {}
        self._base_edit_model: Dict[str, object] = {}
        self._prime_edit_model: Dict[str, object] = {}
        self._variant: Dict[str, object] = {}

    # --- registration ---------------------------------------------------
    def register_variant(self, adapter) -> None:
        self._variant[adapter.name] = adapter

    def register_sequence(self, adapter: base.SequenceProvider) -> None:
        self._sequence[adapter.name] = adapter

    def register_on_target(self, adapter: base.OnTargetScorer) -> None:
        self._on_target[adapter.name] = adapter

    def register_off_target(self, adapter: base.OffTargetScorer) -> None:
        self._off_target[adapter.name] = adapter

    def register_repair(self, adapter: base.RepairOutcomePredictor) -> None:
        self._repair[adapter.name] = adapter

    def register_base_edit_model(self, adapter) -> None:
        self._base_edit_model[adapter.name] = adapter

    def register_prime_edit_model(self, adapter) -> None:
        self._prime_edit_model[adapter.name] = adapter

    # --- lookup ---------------------------------------------------------
    def sequence(self, key: str) -> base.SequenceProvider:
        return _get(self._sequence, key, "sequence provider")

    def on_target(self, key: str) -> base.OnTargetScorer:
        return _get(self._on_target, key, "on-target scorer")

    def off_target(self, key: str) -> base.OffTargetScorer:
        return _get(self._off_target, key, "off-target scorer")

    def repair(self, key: str) -> base.RepairOutcomePredictor:
        return _get(self._repair, key, "repair predictor")

    def base_edit_model(self, key: str):
        return _get(self._base_edit_model, key, "base-edit model")

    def prime_edit_model(self, key: str):
        return _get(self._prime_edit_model, key, "prime-edit model")

    def variant(self, key: str):
        return _get(self._variant, key, "variant provider")

    # --- introspection --------------------------------------------------
    def catalog(self) -> Dict[str, list]:
        """Registered backend keys per role — the selectable `simulate {}` options."""
        return {
            "sequence_provider": sorted(self._sequence),
            "on_target": sorted(self._on_target),
            "off_target": sorted(self._off_target),
            "repair_outcome": sorted(self._repair),
            "base_edit_model": sorted(self._base_edit_model),
            "prime_edit_model": sorted(self._prime_edit_model),
            "variant_source": sorted(self._variant),
        }


def _get(table: dict, key: str, role: str):
    try:
        return table[key]
    except KeyError:
        options = ", ".join(sorted(table)) or "<none>"
        raise KeyError(f"No {role} registered as {key!r}. Available: {options}")


def default_registry() -> AdapterRegistry:
    """A registry preloaded with the offline MVP built-ins."""
    reg = AdapterRegistry()
    reg.register_sequence(builtins.InlineSequenceProvider())
    ensembl = EnsemblSequenceProvider()  # network; used only if named
    ncbi = NcbiSequenceProvider()
    reg.register_sequence(ensembl)
    reg.register_sequence(ncbi)
    # Resilient default: Ensembl (exon-aware), falling back to NCBI if it is down.
    reg.register_sequence(FallbackSequenceProvider(ensembl, ncbi))
    reg.register_on_target(builtins.HeuristicOnTargetScorer())
    reg.register_on_target(RuleSet1OnTargetScorer())  # Doench 2014, real model
    reg.register_off_target(builtins.MockOffTargetScorer())
    # Real off-target: Cas-OFFinder scan + CFD. Configured from env (HELIX_GENOME_DIR,
    # HELIX_CASOFFINDER_BIN); errors with guidance at scan time if unset.
    reg.register_off_target(CasOffinderCfdScorer(CasOffinderRunner.from_env()))
    reg.register_repair(builtins.MockRepairOutcomePredictor())
    # Real repair outcomes: inDelphi (lazy import; errors with guidance if absent).
    reg.register_repair(InDelphiRepairPredictor(InDelphiBackend(celltype="mESC")))

    # Learned outcome models for base/prime editing (heuristic default + real ML).
    reg.register_base_edit_model(HeuristicBaseEditBackend())
    reg.register_base_edit_model(BEHiveBackend())
    reg.register_prime_edit_model(HeuristicPrimeEditBackend())
    reg.register_prime_edit_model(PridictBackend())

    # Population-variant awareness (default off; `ensembl` needs a database-resolved target).
    from helix.adapters.variants import EnsemblVariantProvider, NullVariantProvider

    reg.register_variant(NullVariantProvider())
    reg.register_variant(EnsemblVariantProvider())
    return reg
