"""Load and validate a Helix spec, from either frontend.

Two surfaces compile to the *same* :class:`ExperimentSpec` IR:

* ``.hx`` / ``.helix`` — the Helix grammar (see :mod:`helix.frontend.helix_lang`)
* ``.yaml`` / ``.yml`` — YAML, handy for machine-generated specs

All roads funnel through :func:`spec_from_dict`, so validation and DSL-surface
aliases live in exactly one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Union

import yaml

from helix.ir.spec import ExperimentSpec

# DSL-surface keys that differ from IR field names, kept friendly for authors.
_ALIASES = {"validate": "validate_with"}


def spec_from_dict(data: Dict[str, Any]) -> ExperimentSpec:
    """Validate a decoded mapping into an ``ExperimentSpec`` (shared by all frontends)."""
    if not isinstance(data, dict):
        raise ValueError("Helix spec must be a mapping at the top level.")
    for surface, field in _ALIASES.items():
        if surface in data:
            data[field] = data.pop(surface)
    return ExperimentSpec.model_validate(data)


def parse_spec(raw: Union[str, Dict[str, Any]]) -> ExperimentSpec:
    """Parse a spec from a YAML string or an already-decoded mapping."""
    data = yaml.safe_load(raw) if isinstance(raw, str) else raw
    return spec_from_dict(data)


def load_spec(path: Union[str, Path]) -> ExperimentSpec:
    """Load a spec from disk, choosing the frontend by file extension."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".hx", ".helix"):
        from helix.frontend.helix_lang import parse_helix  # local: avoid import cycle

        return parse_helix(text)
    return parse_spec(text)
