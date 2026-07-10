"""Gene-database connectors — load the *proper* gene from a source of truth.

A :class:`GeneDatabase` resolves a gene symbol into a real record (coordinates,
strand, canonical transcript, exons) and fetches sequence for a region. On top of
that, :class:`GeneResolver` turns a spec's ``gene`` + ``region`` into an edit
window — so ``region: exon(2..4)`` becomes actual exon coordinates rather than a
guessed window.

Backends sit behind an injectable HTTP transport (offline-testable), and a
:class:`CachingGeneDatabase` wrapper avoids repeat lookups. Ensembl is wired;
NCBI is a documented extension point implementing the same Protocol.
"""

from helix.databases.base import GeneDatabase, GeneDatabaseError
from helix.databases.cache import CachingGeneDatabase
from helix.databases.ensembl import EnsemblDatabase
from helix.databases.models import Exon, GeneRecord, SeqRegion
from helix.databases.resolver import GeneResolver

__all__ = [
    "GeneDatabase",
    "GeneDatabaseError",
    "EnsemblDatabase",
    "CachingGeneDatabase",
    "GeneResolver",
    "GeneRecord",
    "Exon",
    "SeqRegion",
]
