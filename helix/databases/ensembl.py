"""Ensembl REST gene database (injectable HTTP transport)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, List

from helix.bio import normalize
from helix.databases.base import GeneDatabaseError
from helix.databases.models import Exon, GeneRecord, SeqRegion

GetJson = Callable[[str], Dict]

# Ensembl REST occasionally 500s under load and rate-limits with 429; a resilient
# client retries those (and transient network errors) with exponential backoff.
_MAX_RETRIES = 4
_BACKOFF = 0.5
_MAX_DELAY = 10.0

_SPECIES = {
    "human": "homo_sapiens",
    "mouse": "mus_musculus",
    "rat": "rattus_norvegicus",
    "zebrafish": "danio_rerio",
}


def species_slug(organism: str) -> str:
    return _SPECIES.get(organism.strip().lower(), organism.strip().lower())


def _retry_delay(attempt: int, retry_after: str = None) -> float:
    if retry_after and retry_after.strip().isdigit():
        return min(float(retry_after), _MAX_DELAY)
    return min(_BACKOFF * (2 ** attempt), _MAX_DELAY)


def _urllib_get_json(url: str, timeout: float = 10.0) -> Dict:
    """GET JSON with retries on 5xx/429 and transient network failures."""
    req = urllib.request.Request(url, headers={"User-Agent": "helix/0.1", "Accept": "application/json"})
    last = None
    for attempt in range(_MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:  # subclass of URLError — catch first
            last = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt < _MAX_RETRIES - 1:
                after = exc.headers.get("Retry-After") if exc.headers else None
                time.sleep(_retry_delay(attempt, after))
                continue
            raise GeneDatabaseError(f"Ensembl HTTP {exc.code} for {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_retry_delay(attempt))
                continue
            raise GeneDatabaseError(f"Ensembl request failed: {url} ({exc})") from exc
    raise GeneDatabaseError(f"Ensembl request failed after {_MAX_RETRIES} attempts: {url} ({last})")


class EnsemblDatabase:
    name = "ensembl"

    def __init__(self, host: str = "https://rest.ensembl.org", get_json: GetJson = _urllib_get_json):
        self.host = host.rstrip("/")
        self._get_json = get_json
        self.version = host.split("//")[-1].rstrip("/")

    def lookup(self, symbol: str, species: str) -> GeneRecord:
        info = self._get_json(
            f"{self.host}/lookup/symbol/{species}/{symbol}?expand=1;content-type=application/json"
        )
        for key in ("seq_region_name", "start", "end", "strand"):
            if key not in info:
                raise GeneDatabaseError(f"Ensembl lookup for {symbol!r} missing '{key}'.")
        strand = int(info["strand"])
        exons = _canonical_exons(info.get("Transcript", []), strand)
        return GeneRecord(
            symbol=symbol,
            gene_id=info.get("id", ""),
            chrom=str(info["seq_region_name"]),
            start=int(info["start"]),
            end=int(info["end"]),
            strand=strand,
            assembly=info.get("assembly_name"),
            biotype=info.get("biotype"),
            canonical_transcript=_canonical_id(info.get("Transcript", [])),
            exons=exons,
        )

    def sequence(self, region: SeqRegion, species: str) -> str:
        payload = self._get_json(
            f"{self.host}/sequence/region/{species}/{region.ensembl_region()}?content-type=application/json"
        )
        seq = normalize(payload.get("seq", ""))
        if not seq:
            raise GeneDatabaseError(f"Ensembl returned no sequence for {region.ensembl_region()}.")
        return seq


def _canonical_transcript(transcripts: List[Dict]) -> Dict:
    for t in transcripts:
        if t.get("is_canonical") in (1, True, "1"):
            return t
    return transcripts[0] if transcripts else {}


def _canonical_id(transcripts: List[Dict]):
    return _canonical_transcript(transcripts).get("id") if transcripts else None


def _canonical_exons(transcripts: List[Dict], strand: int) -> List[Exon]:
    exons = _canonical_transcript(transcripts).get("Exon", []) if transcripts else []
    if not exons:
        return []
    # Ensembl returns exons in ascending genomic order; biological rank runs 5'->3'.
    ordered = sorted(exons, key=lambda e: int(e["start"]), reverse=(strand == -1))
    return [Exon(rank=i + 1, start=int(e["start"]), end=int(e["end"])) for i, e in enumerate(ordered)]
