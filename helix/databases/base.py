"""The GeneDatabase Protocol shared by all connectors."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from helix.databases.models import GeneRecord, SeqRegion


class GeneDatabaseError(RuntimeError):
    """Raised when a database is unreachable or returns an unexpected payload."""


@runtime_checkable
class GeneDatabase(Protocol):
    name: str

    def lookup(self, symbol: str, species: str) -> GeneRecord:
        """Resolve a gene symbol into a record (coords, strand, exons)."""
        ...

    def sequence(self, region: SeqRegion, species: str) -> str:
        """Fetch the DNA sequence (5'->3', region strand) for a genomic region."""
        ...
