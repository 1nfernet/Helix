"""The Helix intermediate representation (IR).

Two families of typed models:

* :mod:`helix.ir.spec` — the *intent* layer, i.e. the parsed DSL. This is what a
  user writes and reviews in version control.
* :mod:`helix.ir.design` — the *compiler output* layer, i.e. the fully resolved
  design with scored guides, reports, and provenance.

Keeping these separate is the core architectural decision of Helix: the spec is
small and human-authored; the design is large and machine-generated. LLM agents
may only ever *emit or edit a spec*; the deterministic compiler owns the design.
"""

from helix.ir import design, enums, spec

__all__ = ["spec", "design", "enums"]
