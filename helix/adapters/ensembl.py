"""Ensembl sequence provider — a thin ``SequenceProvider`` over the gene database.

Delegates to :mod:`helix.databases` so it resolves the *proper* gene region
(exon-aware via ``region: exon(2..4)``) with caching and retry/backoff, while
keeping the original injectable ``get_json`` transport and ``ensembl`` registry
name. Routes GRCh38 and GRCh37 to their respective REST hosts.
"""

from __future__ import annotations

from typing import Dict

from helix.databases.base import GeneDatabaseError as EnsemblError  # back-compat alias
from helix.databases.cache import CachingGeneDatabase
from helix.databases.ensembl import EnsemblDatabase, GetJson, _urllib_get_json
from helix.databases.resolver import GeneResolver
from helix.ir.design import ResolvedTarget
from helix.ir.spec import ExperimentSpec

__all__ = ["EnsemblSequenceProvider", "EnsemblError"]

_HOSTS = {
    "GRCh38": "https://rest.ensembl.org",
    "GRCh37": "https://grch37.rest.ensembl.org",
}


class EnsemblSequenceProvider:
    name = "ensembl"
    version = "rest.ensembl.org"

    def __init__(
        self,
        window_length: int = 300,
        host: str = None,  # override auto host selection (e.g. for tests)
        get_json: GetJson = _urllib_get_json,
    ):
        self._window_length = window_length
        self._forced_host = host
        self._get_json = get_json
        self._resolvers: Dict[str, GeneResolver] = {}

    def _resolver(self, host: str) -> GeneResolver:
        if host not in self._resolvers:
            db = CachingGeneDatabase(EnsemblDatabase(host=host, get_json=self._get_json))
            self._resolvers[host] = GeneResolver(db, window_length=self._window_length)
        return self._resolvers[host]

    def resolve(self, spec: ExperimentSpec) -> ResolvedTarget:
        host = self._forced_host or _HOSTS.get(spec.genome_build)
        if host is None:
            raise EnsemblError(
                f"No Ensembl REST host for build {spec.genome_build!r}; supported: "
                f"{', '.join(sorted(_HOSTS))}."
            )
        return self._resolver(host).resolve(spec)
