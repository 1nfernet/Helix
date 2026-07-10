"""Tests for the FastAPI backend (offline via TestClient)."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from helix.server.app import app  # noqa: E402

client = TestClient(app)


def _ko_source():
    src = client.get("/api/examples").json()
    return next(e["source"] for e in src if e["name"] == "tp53_ko" and e["format"] == "helix")


def test_health():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert "ai_configured" in body  # UI gates the AI features on this


def test_api_routes_win_over_static_mount():
    # The built web UI is served from "/", but /api/* routes must still resolve
    # (the static mount is registered last so it never shadows the API).
    assert client.get("/api/health").status_code == 200
    from helix.server.app import _FRONTEND_DIST

    root = client.get("/")
    if _FRONTEND_DIST.is_dir():
        assert root.status_code == 200 and "text/html" in root.headers.get("content-type", "")
    # else: no build present — the API-only server is a valid deployment too.


# --- LLM agent endpoints (fake client injected; no key/network) ---------

import importlib  # noqa: E402

appmod = importlib.import_module("helix.server.app")


class _FakeLLM:
    def __init__(self, reply):
        self._reply = reply
        self.model = "claude-haiku-4-5-20251001"
        self.last_usage = {"input_tokens": 1000, "output_tokens": 200,
                           "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}

    def complete(self, system, user, *, max_tokens=1024):
        return self._reply


def test_author_endpoint_returns_validated_spec(monkeypatch):
    src = _ko_source()
    monkeypatch.setattr(appmod, "_llm", lambda model=None: _FakeLLM(src))
    r = client.post("/api/author", json={"request": "knock out TP53 in HEK293T"})
    assert r.status_code == 200
    b = r.json()
    assert b["format"] == "helix" and "helix" in b["source"]
    assert b["cost"] is not None and b["usage"]["input_tokens"] == 1000


def test_critique_endpoint_patches_constraints(monkeypatch):
    reply = ('{"summary":"tighten specificity","findings":[{"severity":"warning",'
             '"category":"offtarget","message":"CFD margin thin","suggestion":"lower it"}],'
             '"suggested_constraint_edits":{"off_target_max_cfd":0.1}}')
    monkeypatch.setattr(appmod, "_llm", lambda model=None: _FakeLLM(reply))
    r = client.post("/api/critique", json={"source": _ko_source(), "format": "helix"})
    assert r.status_code == 200
    b = r.json()
    assert b["summary"] == "tighten specificity"
    assert b["findings"][0]["severity"] == "warning"
    assert b["suggested_constraint_edits"]["off_target_max_cfd"] == 0.1
    assert "off_target.max_cfd: 0.1" in b["revised_source"]  # applied to the spec text


def test_adapters_endpoint_lists_connectable_models():
    roles = client.get("/api/adapters").json()["roles"]
    by_label = {r["label"]: r for r in roles}
    assert {"sequence provider", "on-target efficiency", "off-target scan",
            "repair outcome", "structure / folding"} <= set(by_label)
    # each role advertises its simulate {} key and provenance key for the UI
    ot = by_label["on-target efficiency"]
    assert ot["sim_key"] == "on_target" and ot["prov_key"] == "on_target"
    kinds = {a["key"]: a["kind"] for a in ot["options"]}
    assert kinds["rule_set_1"] == "verified"
    fold = {a["key"]: a for a in by_label["structure / folding"]["options"]}
    assert fold["esmfold"]["kind"] == "remote"
    # external tools carry a setup hint so the UI can tell users how to enable them
    cas = {a["key"]: a for a in by_label["off-target scan"]["options"]}["cas_offinder_cfd"]
    assert "setup" in cas and "HELIX_GENOME_DIR" in cas["setup"]


def test_esmfold_plddt_normalizes_to_0_100():
    from helix.structure.esmfold import mean_plddt

    pdb = (
        "ATOM      1  CA  MET A   1      0.000   0.000   0.000  1.00  0.90           C\n"
        "ATOM      2  CA  LYS A   2      1.000   0.000   0.000  1.00  0.80           C\n"
    )
    assert mean_plddt(pdb) == 85.0  # (0.90+0.80)/2 -> 0.85 -> 85.0


def test_structure_endpoint_assembles_design_complex():
    design = client.post("/api/compile", json={"source": _ko_source(), "format": "helix"}).json()["design"]
    r = client.post("/api/structure", json={"design": design})
    assert r.status_code == 200
    b = r.json()
    assert b["available"] is True and b["reference_pdb"] == "4OO8"
    assert {c["type"] for c in b["chains"]} == {"protein", "rna", "dna"}
    assert b["confidence"] is None and b["backend"] == "not configured"  # no folding binary offline
    rna = next(c for c in b["chains"] if c["type"] == "rna")
    assert rna["length"] > 20  # spacer + sgRNA scaffold


def test_patch_source_applies_avoid_and_numeric_edits():
    src = ('helix "x" { target: gene(TP53) { goal: knockout; sequence: "ACGT" } '
           'constraints { off_target.max_cfd: 0.2; avoid: [ homopolymer(>=4) ] } }')
    out = appmod._patch_constraints_source(
        src, "helix", {"off_target_max_cfd": 0.1, "avoid_restriction_sites": ["BsaI", "EcoRI"], "max_homopolymer": 5}
    )
    assert "off_target.max_cfd: 0.1" in out
    assert "homopolymer(>=5)" in out
    assert "restriction_site(BsaI)" in out and "restriction_site(EcoRI)" in out


def test_author_without_key_is_503(monkeypatch):
    from helix.agents.llm import LLMNotConfigured

    class _Unconfigured:
        model = "claude-haiku-4-5-20251001"
        last_usage = None

        def complete(self, *a, **k):
            raise LLMNotConfigured("Set ANTHROPIC_API_KEY to use the Anthropic client.")

    monkeypatch.setattr(appmod, "_llm", lambda model=None: _Unconfigured())
    r = client.post("/api/author", json={"request": "knock out TP53"})
    assert r.status_code == 503 and r.json()["detail"]["type"] == "llm"


def test_examples_lists_specs():
    names = {e["name"] for e in client.get("/api/examples").json()}
    assert {"tp53_ko", "tp53_base_edit", "tp53_prime_edit"} <= names


def test_compile_returns_design_and_protocol():
    r = client.post("/api/compile", json={"source": _ko_source(), "format": "helix"})
    assert r.status_code == 200
    body = r.json()
    assert body["design"]["modality"] == "crispr_ko"
    assert body["design"]["selected"]
    assert body["protocol"].startswith("# Helix design")


def test_compile_syntax_error_is_400_with_location():
    r = client.post("/api/compile", json={"source": 'helix "x" { target: gene(T){ goal x } }',
                                          "format": "helix"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["type"] == "syntax" and detail["line"] == 1 and "col" in detail


def test_compile_error_surfaces_as_400():
    # prime editing without target.edit fails at compile time
    src = 'helix "p" { target: gene(T){ sequence: "ACGT" } strategy { modality: prime_edit } }'
    r = client.post("/api/compile", json={"source": src, "format": "helix"})
    assert r.status_code == 400 and r.json()["detail"]["type"] == "compile"


def test_compile_includes_delivery_recommendation():
    r = client.post("/api/compile", json={"source": _ko_source(), "format": "helix"})
    dv = r.json()["design"]["delivery"]
    assert dv["recommended"] in {"rnp", "plasmid", "lnp", "aav"}
    assert dv["options"] and dv["cargo_kb"] > 0


def test_compile_batch_endpoint():
    ko = _ko_source()
    r = client.post("/api/compile-batch", json={"items": [
        {"source": ko, "format": "helix"},
        {"source": 'helix "x" { target: gene(T){ sequence: "ACGT" } strategy { modality: prime_edit } }', "format": "helix"},
    ]})
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 2
    assert "design" in results[0] and results[0]["design"]["modality"] == "crispr_ko"
    assert results[1].get("error")  # prime edit without target.edit -> per-item error


def test_run_persistence_endpoints(tmp_path, monkeypatch):
    import importlib

    from helix.server.store import RunStore

    appmod = importlib.import_module("helix.server.app")  # real module (not the shadowed `app`)
    monkeypatch.setattr(appmod, "_store", RunStore(str(tmp_path / "runs.json")))
    saved = client.post("/api/runs", json={
        "design": {"spec_name": "srv", "modality": "crispr_ko", "feasible": True,
                   "delivery": {"recommended": "rnp"}},
        "protocol": "# srv",
    }).json()
    rid = saved["id"]
    assert saved["name"] == "srv" and saved["delivery"] == "rnp"
    assert any(x["id"] == rid for x in client.get("/api/runs").json()["runs"])
    assert client.get(f"/api/runs/{rid}").json()["protocol"] == "# srv"
    assert client.delete(f"/api/runs/{rid}").json()["ok"] is True
    assert client.get(f"/api/runs/{rid}").status_code == 404


def test_validate_blocks_germline():
    src = 'helix "g" { cell_line: human embryo\n target: gene(T){ sequence: "ACGT" } }'
    # cell_line with a space isn't valid grammar; use YAML for this check
    r = client.post("/api/validate", json={
        "source": "name: g\ncell_line: human embryo\ntarget: {gene: T, sequence: ACGT}",
        "format": "yaml"})
    assert r.status_code == 200
    assert r.json()["safety"]["allowed"] is False
