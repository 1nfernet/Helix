"""The deterministic compiler — Helix's spine.

``compile_spec`` orchestrates: safety screen -> strategy resolution -> target
resolution -> guide design -> in-silico scoring -> constraint solving ->
validation-primer design -> provenance -> assembled :class:`ResolvedDesign`.

No wall-clock, no RNG, no network in this path (adapters may add those, but the
built-ins are pure). Given the same spec and adapter versions, the design is
reproducible.
"""

from helix.compiler.pipeline import compile_spec

__all__ = ["compile_spec"]
