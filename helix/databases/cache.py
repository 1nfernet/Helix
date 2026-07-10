"""In-memory caching wrapper for any GeneDatabase (avoids repeat lookups)."""

from __future__ import annotations

from typing import Dict, Tuple

from helix.databases.base import GeneDatabase
from helix.databases.models import GeneRecord, SeqRegion


class CachingGeneDatabase:
    """Wrap a GeneDatabase, memoizing lookups and sequence fetches."""

    def __init__(self, inner: GeneDatabase):
        self._inner = inner
        self.name = getattr(inner, "name", "db")
        self.version = getattr(inner, "version", "")
        self._genes: Dict[Tuple[str, str], GeneRecord] = {}
        self._seqs: Dict[str, str] = {}

    def lookup(self, symbol: str, species: str) -> GeneRecord:
        key = (species, symbol.upper())
        if key not in self._genes:
            self._genes[key] = self._inner.lookup(symbol, species)
        return self._genes[key]

    def sequence(self, region: SeqRegion, species: str) -> str:
        key = f"{species}:{region.ensembl_region()}"
        if key not in self._seqs:
            self._seqs[key] = self._inner.sequence(region, species)
        return self._seqs[key]
