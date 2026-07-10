"""Capture everything needed to reproduce or audit a run."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

from helix import __version__
from helix.ir.design import Provenance
from helix.ir.spec import ExperimentSpec


def build_provenance(spec: ExperimentSpec, adapters: Dict[str, str]) -> Provenance:
    return Provenance(
        helix_version=__version__,
        genome_build=spec.genome_build,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        adapters=adapters,
        spec_name=spec.name,
    )
