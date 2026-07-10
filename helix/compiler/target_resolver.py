"""Resolve a spec's target into a concrete edit window.

Thin wrapper over the selected sequence-provider adapter. Kept as its own stage
so the coordinate-based provider (Ensembl) can add caching, build pinning, and
region math here without touching guide design.
"""

from __future__ import annotations

from helix.adapters.base import SequenceProvider
from helix.ir.design import ResolvedTarget
from helix.ir.spec import ExperimentSpec


def resolve_target(spec: ExperimentSpec, provider: SequenceProvider) -> ResolvedTarget:
    target = provider.resolve(spec)
    if target.length < 23:
        raise ValueError(
            f"Edit window for '{target.gene}' is {target.length} nt; need >= 23 "
            "for a 20 nt spacer + NGG PAM."
        )
    # Carry the reading frame from the spec (the window is the coding/sense strand)
    # unless the provider already determined it.
    if target.frame is None and spec.target.frame is not None:
        target = target.model_copy(update={"frame": spec.target.frame})
    return target
