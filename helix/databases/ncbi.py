"""NCBI gene database backend — a second `GeneDatabase` source.

Uses NCBI Datasets v2 for gene lookup (coordinates, strand, RefSeq accession) and
E-utilities efetch for sequence. Implements the same Protocol as Ensembl, so it is
selected by `sequence_provider: ncbi` or composed for fallback. Injectable JSON and
text transports keep it offline-testable; both retry on 5xx/429/transient errors.

Exon-level resolution is Ensembl's (NCBI here returns gene-level windows); the
resolver falls back to a gene-start window when exons are absent.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable, Dict

from helix.bio import normalize
from helix.databases.base import GeneDatabaseError
from helix.databases.models import GeneRecord, SeqRegion

_DATASETS = "https://api.ncbi.nlm.nih.gov/datasets/v2alpha"
_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Ensembl species slug -> NCBI taxon id.
_TAXON = {
    "homo_sapiens": "9606",
    "mus_musculus": "10090",
    "rattus_norvegicus": "10116",
    "danio_rerio": "7955",
}

_MAX_RETRIES = 4
_BACKOFF = 0.5
_MAX_DELAY = 10.0

GetJson = Callable[[str], Dict]
GetText = Callable[[str], str]


def _retry(fetch, url: str):
    last = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fetch(url)
        except urllib.error.HTTPError as exc:
            last = exc
            if (exc.code == 429 or 500 <= exc.code < 600) and attempt < _MAX_RETRIES - 1:
                after = exc.headers.get("Retry-After") if exc.headers else None
                time.sleep(min(float(after), _MAX_DELAY) if (after and after.isdigit())
                           else min(_BACKOFF * 2 ** attempt, _MAX_DELAY))
                continue
            raise GeneDatabaseError(f"NCBI HTTP {exc.code} for {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(min(_BACKOFF * 2 ** attempt, _MAX_DELAY))
                continue
            raise GeneDatabaseError(f"NCBI request failed: {url} ({exc})") from exc
    raise GeneDatabaseError(f"NCBI request failed after {_MAX_RETRIES} attempts: {url} ({last})")


def _http_get_json(url: str) -> Dict:
    def _fetch(u):
        req = urllib.request.Request(u, headers={"User-Agent": "helix/0.1", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    return _retry(_fetch, url)


def _http_get_text(url: str) -> str:
    def _fetch(u):
        req = urllib.request.Request(u, headers={"User-Agent": "helix/0.1"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "replace")
    return _retry(_fetch, url)


class NcbiDatabase:
    name = "ncbi"

    def __init__(
        self,
        assembly: str = "GRCh38",
        get_json: GetJson = _http_get_json,
        get_text: GetText = _http_get_text,
    ):
        self.assembly = assembly
        self.version = "api.ncbi.nlm.nih.gov"
        self._get_json = get_json
        self._get_text = get_text

    def lookup(self, symbol: str, species: str) -> GeneRecord:
        taxon = _TAXON.get(species)
        if taxon is None:
            raise GeneDatabaseError(f"No NCBI taxon mapping for species {species!r}.")
        data = self._get_json(f"{_DATASETS}/gene/symbol/{symbol}/taxon/{taxon}")
        reports = data.get("reports") or []
        if not reports:
            raise GeneDatabaseError(f"NCBI has no gene for symbol {symbol!r}.")
        gene = reports[0].get("gene", {})
        loc = _location_for(gene, self.assembly, symbol)
        gr = loc["genomic_range"]
        strand = -1 if gr.get("orientation") == "minus" else 1
        return GeneRecord(
            symbol=gene.get("symbol", symbol),
            gene_id=str(gene.get("gene_id", "")),
            chrom=loc["genomic_accession_version"],  # RefSeq accession, e.g. NC_000017.11
            start=int(gr["begin"]),
            end=int(gr["end"]),
            strand=strand,
            assembly=self.assembly,
            biotype=gene.get("type"),
            canonical_transcript=None,
            exons=[],  # gene-level; exon resolution is Ensembl's
        )

    def sequence(self, region: SeqRegion, species: str) -> str:
        strand = 2 if region.strand == -1 else 1
        url = (
            f"{_EUTILS}/efetch.fcgi?db=nuccore&id={region.chrom}&rettype=fasta&retmode=text"
            f"&seq_start={region.start}&seq_stop={region.end}&strand={strand}"
        )
        text = self._get_text(url)
        seq = normalize("".join(l for l in text.splitlines() if l and not l.startswith(">")))
        if not seq:
            raise GeneDatabaseError(f"NCBI returned no sequence for {region.chrom}:{region.start}-{region.end}.")
        return seq


def _location_for(gene: Dict, assembly: str, symbol: str) -> Dict:
    for ann in gene.get("annotations", []):
        if str(ann.get("assembly_name", "")).startswith(assembly):
            locs = ann.get("genomic_locations") or []
            if locs:
                return locs[0]
    raise GeneDatabaseError(f"NCBI has no {assembly} annotation for {symbol!r}.")
