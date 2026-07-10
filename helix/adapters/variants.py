"""Variant providers — known population variants overlapping the target window.

A common SNP in a guide's seed or PAM abolishes binding in carriers, so a
therapeutic/portable guide should avoid one. Behind the injectable ``get_json``
transport, :class:`EnsemblVariantProvider` queries Ensembl's variation overlap
and maps each variant to a window coordinate; :class:`StaticVariantProvider`
serves a fixed list offline (tests), and :class:`NullVariantProvider` (the
default) returns none so the deterministic path needs no network.
"""

from __future__ import annotations

from typing import List, Optional

from helix.ir.design import ResolvedTarget, SeqVariant

_ENSEMBL_HOSTS = {"GRCh38": "https://rest.ensembl.org", "GRCh37": "https://grch37.rest.ensembl.org"}


class NullVariantProvider:
    name = "none"
    version = "0"

    def variants(self, target: ResolvedTarget) -> List[SeqVariant]:
        return []


class StaticVariantProvider:
    """Offline provider from a fixed list of window-coordinate variants."""

    name = "static"
    version = "0"

    def __init__(self, variants: List[SeqVariant]):
        self._variants = list(variants)

    def variants(self, target: ResolvedTarget) -> List[SeqVariant]:
        return [v for v in self._variants if 0 <= v.window_pos < target.length]


class EnsemblVariantProvider:
    name = "ensembl"
    version = "rest.ensembl.org/overlap"

    def __init__(self, get_json=None, host: Optional[str] = None):
        if get_json is None:
            from helix.databases.ensembl import _urllib_get_json

            get_json = _urllib_get_json
        self._get_json = get_json
        self._forced_host = host

    def variants(self, target: ResolvedTarget) -> List[SeqVariant]:
        loc = target.locus
        if loc is None:  # inline sequence — no genomic coordinates to query
            return []
        host = self._forced_host or _ENSEMBL_HOSTS.get(target.genome_build)
        if host is None:
            return []
        url = (
            f"{host}/overlap/region/homo_sapiens/{loc.chromosome}:{loc.start}-{loc.end}"
            "?feature=variation;content-type=application/json"
        )
        try:
            data = self._get_json(url)
        except Exception:  # network / parse failure — degrade to no variants, never break a run
            return []
        out: List[SeqVariant] = []
        for v in data or []:
            try:
                gpos = int(v.get("start"))
            except (TypeError, ValueError):
                continue
            wp = (gpos - loc.start) if loc.strand == 1 else (loc.end - gpos)
            if not (0 <= wp < target.length):
                continue
            freq = v.get("minor_allele_frequency")
            alleles = v.get("alleles")
            out.append(SeqVariant(
                id=str(v.get("id", "")),
                window_pos=wp,
                alleles="/".join(alleles) if isinstance(alleles, list) else str(alleles or ""),
                frequency=float(freq) if isinstance(freq, (int, float)) else None,
            ))
        return out
