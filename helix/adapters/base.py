"""Adapter Protocols — the contracts the compiler programs against.

These are structural (:class:`typing.Protocol`) rather than base classes on
purpose: a real tool wrapper does not need to import Helix to satisfy an
interface, it just needs the right method shape. That keeps third-party tool
integrations loosely coupled.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from typing import List

from helix.ir.design import OffTargetReport, RepairOutcome, ResolvedTarget, SeqVariant
from helix.ir.spec import ExperimentSpec


class ScorerContextError(ValueError):
    """Raised when a scorer lacks the sequence context it needs for a guide.

    e.g. a model requiring a 30-mer cannot score a guide within a few nt of the
    edit-window edge. The compiler catches this and drops the affected guide
    rather than fabricating a score.
    """


@runtime_checkable
class Adapter(Protocol):
    """Common identity used for provenance."""

    name: str
    version: str


@runtime_checkable
class SequenceProvider(Adapter, Protocol):
    def resolve(self, spec: ExperimentSpec) -> ResolvedTarget:
        """Return the edit-window sequence for the spec's target."""
        ...


@runtime_checkable
class OnTargetScorer(Adapter, Protocol):
    def score(self, spacer: str, context: str) -> float:
        """Return on-target cutting efficiency in [0, 1].

        ``context`` is the local genomic sequence around the protospacer, which
        real models (Rule Set 2, DeepSpCas9) require.
        """
        ...


@runtime_checkable
class OffTargetScorer(Adapter, Protocol):
    def scan(self, spacer: str, genome_build: str) -> OffTargetReport:
        """Return an off-target report for ``spacer`` against a genome."""
        ...


@runtime_checkable
class RepairOutcomePredictor(Adapter, Protocol):
    def predict(self, sequence: str, cutsite: int) -> RepairOutcome:
        """Predict the DSB repair genotype distribution at the cut site.

        ``sequence`` is a local DNA window (5'->3'); ``cutsite`` is the 0-based
        index such that the blunt cut falls between ``sequence[cutsite-1]`` and
        ``sequence[cutsite]`` (inDelphi's convention: the number of bases 5' of
        the cut).
        """
        ...


@runtime_checkable
class VariantProvider(Adapter, Protocol):
    def variants(self, target: ResolvedTarget) -> List[SeqVariant]:
        """Known population variants overlapping the target window (window coords)."""
        ...
