"""The DSL frontend: surface syntax -> :class:`helix.ir.spec.ExperimentSpec`.

For the MVP the surface is YAML. A purpose-built grammar (the "Helix" language)
can be added later as an alternative frontend that produces the same IR, so the
compiler is unaffected by syntax choices.
"""

from helix.frontend.loader import load_spec, parse_spec

__all__ = ["load_spec", "parse_spec"]
