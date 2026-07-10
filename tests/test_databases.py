"""Tests for the gene-database connector (offline, fake HTTP)."""

import pytest

from helix.databases.cache import CachingGeneDatabase
from helix.databases.ensembl import EnsemblDatabase
from helix.databases.resolver import GeneResolver, parse_exon_region
from helix.frontend.loader import parse_spec

# TP53-like gene on the minus strand with three exons (ascending genomic order).
_LOOKUP = {
    "id": "ENSG_TEST",
    "seq_region_name": "17",
    "start": 7661779,
    "end": 7687546,
    "strand": -1,
    "assembly_name": "GRCh38",
    "biotype": "protein_coding",
    "Transcript": [
        {
            "id": "ENST_CANON",
            "is_canonical": 1,
            "Exon": [
                {"id": "e_a", "start": 7661779, "end": 7662000},
                {"id": "e_b", "start": 7670000, "end": 7670100},
                {"id": "e_c", "start": 7687000, "end": 7687546},
            ],
        }
    ],
}


def _fake_get_json(url):
    if "/lookup/symbol/" in url:
        return dict(_LOOKUP)
    if "/sequence/region/" in url:
        return {"seq": "ACGT" * 40, "molecule": "dna"}  # 160 nt
    raise AssertionError(url)


def test_parse_exon_region():
    assert parse_exon_region("exon 2-4") == [2, 3, 4]
    assert parse_exon_region("exon 3") == [3]
    assert parse_exon_region(None) == []
    assert parse_exon_region("whole gene") == []


def test_lookup_ranks_exons_by_strand():
    gene = EnsemblDatabase(get_json=_fake_get_json).lookup("TP53", "homo_sapiens")
    assert gene.strand == -1 and gene.canonical_transcript == "ENST_CANON"
    # minus strand: highest genomic start is biological exon 1
    assert gene.exon(1).start == 7687000
    assert gene.exon(3).start == 7661779


def test_resolver_uses_exon_coordinates():
    db = EnsemblDatabase(get_json=_fake_get_json)
    spec = parse_spec({"name": "e", "target": {"gene": "TP53", "region": "exon 2"}})
    target = GeneResolver(db, exon_flank=30).resolve(spec)
    # exon 2 = start 7670000, end 7670100; +/- 30 flank
    assert "17:7669970-7670130:-1" in target.source
    assert "exon 2" in target.source
    assert target.length == 160


def test_resolver_falls_back_to_gene_window_without_region():
    db = EnsemblDatabase(get_json=_fake_get_json)
    spec = parse_spec({"name": "e", "target": {"gene": "TP53"}})
    target = GeneResolver(db, window_length=300).resolve(spec)
    assert "17:7661779-7662078:-1" in target.source
    assert "gene-start window" in target.source


def test_caching_avoids_repeat_lookups():
    calls = {"n": 0}

    def counting_get_json(url):
        if "/lookup/symbol/" in url:
            calls["n"] += 1
        return _fake_get_json(url)

    db = CachingGeneDatabase(EnsemblDatabase(get_json=counting_get_json))
    db.lookup("TP53", "homo_sapiens")
    db.lookup("TP53", "homo_sapiens")
    assert calls["n"] == 1


class _FakeResp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b'{"ok": true}'


def test_get_json_retries_on_500_then_succeeds(monkeypatch):
    import helix.databases.ensembl as em

    calls = {"n": 0}

    def fake_urlopen(req, timeout=10.0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise em.urllib.error.HTTPError(req.full_url, 500, "err", None, None)
        return _FakeResp()

    monkeypatch.setattr(em.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(em.time, "sleep", lambda s: None)
    assert em._urllib_get_json("http://x")["ok"] is True
    assert calls["n"] == 3  # retried twice, succeeded on the third


def test_get_json_gives_up_after_retries(monkeypatch):
    import helix.databases.ensembl as em
    from helix.databases.base import GeneDatabaseError

    def always_500(req, timeout=10.0):
        raise em.urllib.error.HTTPError(req.full_url, 503, "down", None, None)

    monkeypatch.setattr(em.urllib.request, "urlopen", always_500)
    monkeypatch.setattr(em.time, "sleep", lambda s: None)
    with pytest.raises(GeneDatabaseError):
        em._urllib_get_json("http://x")


def test_assembly_mismatch_raises():
    from helix.databases.base import GeneDatabaseError

    db = EnsemblDatabase(get_json=_fake_get_json)
    spec = parse_spec({"name": "e", "genome_build": "GRCh37", "target": {"gene": "TP53"}})
    with pytest.raises(GeneDatabaseError):
        GeneResolver(db).resolve(spec)
