"""Batch and library compilation.

* ``compile_batch`` compiles many specs independently, isolating per-spec errors —
  the basis for multiplexed / pooled designs and the UI's batch mode.
* ``library_specs`` expands one base spec across a list of genes (a knockout/edit
  library), clearing the inline sequence so each gene resolves via a database
  provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from helix.adapters.registry import AdapterRegistry, default_registry
from helix.agents.strategy import DeterministicStrategyResolver, StrategyResolver
from helix.compiler.pipeline import compile_spec
from helix.ir.design import ResolvedDesign
from helix.ir.spec import ExperimentSpec


@dataclass
class BatchOutcome:
    name: str
    design: Optional[ResolvedDesign]
    error: Optional[str]


def compile_batch(
    specs: List[ExperimentSpec],
    registry: Optional[AdapterRegistry] = None,
    strategy: Optional[StrategyResolver] = None,
) -> List[BatchOutcome]:
    reg = registry or default_registry()
    strat = strategy or DeterministicStrategyResolver()
    outcomes: List[BatchOutcome] = []
    for spec in specs:
        try:
            outcomes.append(BatchOutcome(spec.name, compile_spec(spec, registry=reg, strategy=strat), None))
        except Exception as exc:
            outcomes.append(BatchOutcome(spec.name, None, str(exc)))
    return outcomes


def library_specs(base: ExperimentSpec, genes: List[str]) -> List[ExperimentSpec]:
    """One spec per gene, sharing the base's strategy/constraints/simulate settings."""
    out: List[ExperimentSpec] = []
    for gene in genes:
        data = base.model_dump()
        data["name"] = f"{base.name}__{gene}"
        data["target"]["gene"] = gene
        data["target"]["sequence"] = None  # resolve each gene via the provider
        # A cross-gene library needs a database provider, not an inline sequence.
        if data["simulate"]["sequence_provider"] == "inline":
            data["simulate"]["sequence_provider"] = "ensembl"
        out.append(ExperimentSpec.model_validate(data))
    return out
