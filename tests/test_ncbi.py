"""Tests for the NCBI gene database backend and the fallback provider (offline)."""

import pytest

from helix.adapters.ncbi import FallbackSequenceProvider, NcbiSequenceProvider
from helix.databases.base import GeneDatabaseError
from helix.databases.models import SeqRegion
from helix.databases.ncbi import NcbiDatabase
from helix.frontend.loader import parse_spec
from helix.ir.design import ResolvedTarget

_REPORT = {
    "reports": [
        {
            "gene": {
                "gene_id": 7157,
                "symbol": "TP53",
                "type": "PROTEIN_CODING",
                "annotations": [
                    {
                        "assembly_name": "GRCh38.p14",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000017.11",
                                "sequence_name": "17",
                                "genomic_range": {"begin": "7668421", "end": "7687490", "orientation": "minus"},
                            }
                        ],
                    },
                    {
                        "assembly_name": "GRCh37.p13",
                        "genomic_locations": [
                            {
                                "genomic_accession_version": "NC_000017.10",
                                "genomic_range": {"begin": "7571720", "end": "7590868", "orientation": "minus"},
                            }
                        ],
                    },
                ],
            }
        }
    ]
}

_FASTA = ">NC_000017.11:c7668510-7668421 Homo sapiens chromosome 17\n" + "ACGT" * 20 + "\n"


def _json(url):
    if "/gene/symbol/" in url:
        return dict(_REPORT)
    raise AssertionError(url)


def _text(url):
    assert "efetch" in url and "strand=2" in url  # minus strand -> strand=2
    return _FASTA


def test_lookup_picks_requested_assembly():
    db = NcbiDatabase(assembly="GRCh38", get_json=_json, get_text=_text)
    gene = db.lookup("TP53", "homo_sapiens")
    assert gene.gene_id == "7157" and gene.chrom == "NC_000017.11"
    assert gene.start == 7668421 and gene.strand == -1 and gene.assembly == "GRCh38"

    db37 = NcbiDatabase(assembly="GRCh37", get_json=_json, get_text=_text)
    assert db37.lookup("TP53", "homo_sapiens").chrom == "NC_000017.10"


def test_lookup_errors_on_unknown_species_and_missing_assembly():
    db = NcbiDatabase(get_json=_json, get_text=_text)
    with pytest.raises(GeneDatabaseError):
        db.lookup("TP53", "martian")  # no taxon
    db_bad = NcbiDatabase(assembly="hg99", get_json=_json, get_text=_text)
    with pytest.raises(GeneDatabaseError):
        db_bad.lookup("TP53", "homo_sapiens")  # no matching annotation


def test_sequence_parses_fasta():
    db = NcbiDatabase(get_json=_json, get_text=_text)
    seq = db.sequence(SeqRegion("NC_000017.11", 7668421, 7668500, -1), "homo_sapiens")
    assert seq == "ACGT" * 20


def test_provider_resolves_via_ncbi():
    provider = NcbiSequenceProvider(window_length=80, get_json=_json, get_text=_text)
    spec = parse_spec({"name": "n", "target": {"gene": "TP53"}})
    target = provider.resolve(spec)
    assert target.source.startswith("ncbi@")
    assert target.sequence == "ACGT" * 20


# --- fallback -----------------------------------------------------------


class _Boom:
    name = "down"

    def resolve(self, spec):
        raise GeneDatabaseError("service unavailable")


class _Good:
    name = "up"

    def resolve(self, spec):
        return ResolvedTarget(gene="TP53", genome_build="GRCh38", sequence="ACGT" * 8,
                              length=32, source="up@test")


def test_fallback_uses_next_source_when_first_fails():
    provider = FallbackSequenceProvider(_Boom(), _Good())
    target = provider.resolve(parse_spec({"name": "f", "target": {"gene": "TP53"}}))
    assert target.source == "up@test"


def test_fallback_raises_when_all_fail():
    provider = FallbackSequenceProvider(_Boom(), _Boom())
    with pytest.raises(GeneDatabaseError):
        provider.resolve(parse_spec({"name": "f", "target": {"gene": "TP53"}}))
