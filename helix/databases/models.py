"""Typed records returned by gene databases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SeqRegion:
    chrom: str
    start: int
    end: int
    strand: int  # +1 / -1

    def ensembl_region(self) -> str:
        return f"{self.chrom}:{self.start}-{self.end}:{self.strand}"

    @property
    def length(self) -> int:
        return self.end - self.start + 1


@dataclass
class Exon:
    rank: int  # biological rank (1 = first exon in transcription order)
    start: int
    end: int


@dataclass
class GeneRecord:
    symbol: str
    gene_id: str
    chrom: str
    start: int
    end: int
    strand: int
    assembly: Optional[str] = None
    biotype: Optional[str] = None
    canonical_transcript: Optional[str] = None
    exons: List[Exon] = field(default_factory=list)

    def exon(self, rank: int) -> Optional[Exon]:
        for e in self.exons:
            if e.rank == rank:
                return e
        return None
