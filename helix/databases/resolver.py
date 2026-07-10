"""Resolve a spec's gene + region into a concrete edit window via a database."""

from __future__ import annotations

import re
from typing import List, Optional

from helix.databases.base import GeneDatabase, GeneDatabaseError
from helix.databases.ensembl import species_slug
from helix.databases.models import GeneRecord, SeqRegion
from helix.ir.design import ResolvedTarget, TargetLocus
from helix.ir.spec import ExperimentSpec

_EXON_RE = re.compile(r"exon\s+(\d+)(?:\s*-\s*(\d+))?", re.I)


def parse_exon_region(region: Optional[str]) -> List[int]:
    """'exon 2-4' -> [2, 3, 4]; 'exon 3' -> [3]; anything else -> []."""
    if not region:
        return []
    m = _EXON_RE.search(region)
    if not m:
        return []
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    return list(range(min(lo, hi), max(lo, hi) + 1))


class GeneResolver:
    """Turn a gene symbol (+ optional exon region) into a ``ResolvedTarget``."""

    def __init__(
        self,
        db: GeneDatabase,
        window_length: int = 300,
        exon_flank: int = 30,
        max_window: int = 2000,
    ):
        self.db = db
        self.window_length = window_length
        self.exon_flank = exon_flank
        self.max_window = max_window

    def resolve(self, spec: ExperimentSpec) -> ResolvedTarget:
        species = species_slug(spec.organism)
        gene = self.db.lookup(spec.target.gene, species)
        if gene.assembly and gene.assembly != spec.genome_build:
            raise GeneDatabaseError(
                f"{self.db.name} returned assembly {gene.assembly} for "
                f"{spec.target.gene!r}, expected {spec.genome_build}."
            )
        region, note = self._region_for(gene, spec.target.region)
        seq = self.db.sequence(region, species)
        src = f"{self.db.name}@{getattr(self.db, 'version', '')} ({region.ensembl_region()}; {note})"
        return ResolvedTarget(
            gene=gene.symbol,
            genome_build=spec.genome_build,
            sequence=seq,
            length=len(seq),
            source=src,
            locus=TargetLocus(chromosome=region.chrom, start=region.start, end=region.end, strand=region.strand),
        )

    def _region_for(self, gene: GeneRecord, region_text):
        ranks = parse_exon_region(region_text)
        if ranks and gene.exons:
            exon = gene.exon(ranks[0])
            if exon is not None:
                start = max(1, exon.start - self.exon_flank)
                end = exon.end + self.exon_flank
                if end - start + 1 > self.max_window:
                    end = start + self.max_window - 1
                return SeqRegion(gene.chrom, start, end, gene.strand), f"exon {ranks[0]}"
        # Fallback: a bounded window from the gene's start coordinate.
        w = min(self.window_length, gene.end - gene.start + 1)
        return SeqRegion(gene.chrom, gene.start, gene.start + w - 1, gene.strand), "gene-start window"
