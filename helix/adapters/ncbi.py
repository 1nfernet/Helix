"""NCBI sequence provider + a source-fallback provider.

``NcbiSequenceProvider`` mirrors the Ensembl one over the NCBI backend.
``FallbackSequenceProvider`` tries providers in order and returns the first that
succeeds — so if one source is down (as Ensembl was), another still loads the gene.
Fallback lives at the *provider* level (not the database) because each source's
region coordinates are in its own namespace (Ensembl '17' vs NCBI 'NC_000017.11').
"""

from __future__ import annotations

from typing import Dict

from helix.databases.base import GeneDatabaseError
from helix.databases.cache import CachingGeneDatabase
from helix.databases.ncbi import GetJson, GetText, NcbiDatabase, _http_get_json, _http_get_text
from helix.databases.resolver import GeneResolver
from helix.ir.design import ResolvedTarget
from helix.ir.spec import ExperimentSpec

_ASSEMBLIES = {"GRCh38", "GRCh37"}


class NcbiSequenceProvider:
    name = "ncbi"
    version = "api.ncbi.nlm.nih.gov"

    def __init__(
        self,
        window_length: int = 300,
        get_json: GetJson = _http_get_json,
        get_text: GetText = _http_get_text,
    ):
        self._window_length = window_length
        self._get_json = get_json
        self._get_text = get_text
        self._resolvers: Dict[str, GeneResolver] = {}

    def _resolver(self, assembly: str) -> GeneResolver:
        if assembly not in self._resolvers:
            db = CachingGeneDatabase(
                NcbiDatabase(assembly=assembly, get_json=self._get_json, get_text=self._get_text)
            )
            self._resolvers[assembly] = GeneResolver(db, window_length=self._window_length)
        return self._resolvers[assembly]

    def resolve(self, spec: ExperimentSpec) -> ResolvedTarget:
        if spec.genome_build not in _ASSEMBLIES:
            raise GeneDatabaseError(
                f"NCBI provider supports {sorted(_ASSEMBLIES)}, got {spec.genome_build!r}."
            )
        return self._resolver(spec.genome_build).resolve(spec)


class FallbackSequenceProvider:
    """Try each provider in order; return the first success (resilience across sources)."""

    name = "fallback"

    def __init__(self, *providers):
        if not providers:
            raise ValueError("FallbackSequenceProvider needs at least one provider")
        self._providers = providers
        self.version = "->".join(p.name for p in providers)

    def resolve(self, spec: ExperimentSpec) -> ResolvedTarget:
        errors = []
        for provider in self._providers:
            try:
                return provider.resolve(spec)
            except Exception as exc:  # try the next source
                errors.append(f"{provider.name}: {exc}")
        raise GeneDatabaseError("all sequence providers failed — " + "; ".join(errors))
