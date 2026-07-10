"""Autonomous refine loop: critique → apply validated edits → recompile → repeat.

Closes the design-improvement loop without a human in the middle, while keeping
the safety properties intact: only the critic's *validated* constraint edits are
applied (hallucinated ones were already dropped), and the loop stops on principled
convergence — no new edits, edits that don't change the spec, or a guardrail that
refuses edits which would make a previously-feasible design infeasible. A hard
iteration cap bounds it regardless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from helix.adapters.registry import AdapterRegistry
from helix.agents.critic import Critique, DesignCritic, apply_constraint_edits
from helix.agents.strategy import StrategyResolver
from helix.ir.design import ResolvedDesign
from helix.ir.spec import ExperimentSpec


@dataclass
class RefineStep:
    iteration: int
    critique: Critique
    applied_edits: Dict[str, Any]
    feasible: bool
    selected_count: int
    adopted: bool


@dataclass
class RefineResult:
    spec: ExperimentSpec
    design: ResolvedDesign
    steps: List[RefineStep] = field(default_factory=list)
    converged: bool = False
    reason: str = ""


class RefineLoop:
    def __init__(
        self,
        critic: DesignCritic,
        max_iters: int = 5,
        registry: Optional[AdapterRegistry] = None,
        strategy: Optional[StrategyResolver] = None,
        compile_fn: Optional[Callable] = None,
    ):
        self._critic = critic
        self.max_iters = max_iters
        self._registry = registry
        self._strategy = strategy
        self._compile_fn = compile_fn  # lazily defaults to compile_spec (avoids import cycle)

    def _compile(self, spec: ExperimentSpec) -> ResolvedDesign:
        compile_fn = self._compile_fn
        if compile_fn is None:
            from helix.compiler.pipeline import compile_spec

            compile_fn = compile_spec
        return compile_fn(spec, registry=self._registry, strategy=self._strategy)

    def run(self, spec: ExperimentSpec) -> RefineResult:
        current = spec
        design = self._compile(current)
        steps: List[RefineStep] = []

        for i in range(1, self.max_iters + 1):
            critique = self._critic.review(current, design)
            edits = critique.suggested_constraint_edits

            if not edits:
                return RefineResult(current, design, steps, True, "no further suggested edits")

            new_spec = apply_constraint_edits(current, edits)
            if new_spec.constraints == current.constraints:
                return RefineResult(current, design, steps, True, "edits do not change the spec")

            new_design = self._compile(new_spec)

            # Guardrail: don't adopt edits that break a feasible design.
            if design.feasible and not new_design.feasible:
                steps.append(RefineStep(i, critique, edits, new_design.feasible,
                                        len(new_design.selected), adopted=False))
                return RefineResult(
                    current, design, steps, True,
                    "stopped: further edits would make the design infeasible",
                )

            steps.append(RefineStep(i, critique, edits, new_design.feasible,
                                    len(new_design.selected), adopted=True))
            current, design = new_spec, new_design

        return RefineResult(current, design, steps, False, f"hit max_iters={self.max_iters}")
