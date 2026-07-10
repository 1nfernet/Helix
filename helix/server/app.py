"""Helix HTTP API (FastAPI)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from helix import __version__
from helix.agents.authoring import SpecAuthor, SpecAuthoringError
from helix.agents.critic import DesignCritic
from helix.agents.llm import AnthropicClient, LLMNotConfigured, estimate_cost, llm_configured
from helix.compiler.batch import compile_batch, library_specs
from helix.compiler.pipeline import compile_spec
from helix.frontend.errors import SpecError, parse_source
from helix.report.bundle import render_markdown
from helix.safety.screen import BiosecurityScreen
from helix.server.store import RunStore

_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
_store = RunStore(os.environ.get("HELIX_RUNS_PATH") or str(Path.home() / ".helix" / "runs.json"))

app = FastAPI(title="Helix", version=__version__)

# The dev frontend runs on a different origin (Vite on :5173); allow it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CompileRequest(BaseModel):
    source: str
    format: str = "helix"  # "helix" | "yaml"


class BatchRequest(BaseModel):
    items: List[CompileRequest]


class LibraryRequest(BaseModel):
    source: str
    format: str = "helix"
    genes: List[str]


class SaveRunRequest(BaseModel):
    design: Dict[str, Any]
    protocol: str = ""


class AuthorRequest(BaseModel):
    request: str
    model: Optional[str] = None


class CritiqueRequest(BaseModel):
    source: str
    format: str = "helix"
    model: Optional[str] = None


class StructureRequest(BaseModel):
    design: Dict[str, Any]


class ResolveRequest(BaseModel):
    gene: str
    build: str = "GRCh38"
    provider: str = "ensembl"  # ensembl | ncbi | fallback


class FoldRequest(BaseModel):
    region: str = "hnh"  # SpCas9 domain to fold with ESMFold


class AnalyzeRequest(BaseModel):
    design: Dict[str, Any]
    reads: str
    reference: Optional[str] = None


class ExampleOut(BaseModel):
    name: str
    format: str
    source: str


def _parse(source: str, fmt: str):
    return parse_source(source, fmt)


def _parse_or_400(source: str, fmt: str):
    try:
        return _parse(source, fmt)
    except SpecError as exc:
        detail = {"type": exc.kind, "message": exc.message}
        if exc.line is not None:
            detail["line"] = exc.line
            detail["col"] = exc.col
        raise HTTPException(status_code=400, detail=detail)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "ai_configured": llm_configured(),
        # True when the offline canned client is in use (no real key) — the UI labels
        # AI output as demo so canned drafts aren't mistaken for real model responses.
        "ai_demo": bool(os.environ.get("HELIX_FAKE_LLM")) and not os.environ.get("ANTHROPIC_API_KEY"),
    }


# --- LLM agents (opt-in; require ANTHROPIC_API_KEY) ---------------------

# Tests replace this factory with a fake client; production builds the real one.
# HELIX_FAKE_LLM swaps in an offline canned client for demos without a key.
def _llm(model: Optional[str] = None):
    if os.environ.get("HELIX_FAKE_LLM"):
        from helix.agents.demo import DemoLLMClient

        return DemoLLMClient(model=model)
    return AnthropicClient(model=model)


_HELIX_CONSTRAINT_KEY = {
    "on_target_min_efficiency": "on_target.min_efficiency",
    "off_target_max_cfd": "off_target.max_cfd",
    "guides_count": "guides.count",
}


def _patch_constraints_source(source: str, fmt: str, edits: Dict[str, Any]) -> str:
    """Apply validated constraint edits to the spec *text* so the editor stays the
    source of truth (numeric knobs + the homopolymer bound; others stay advisory)."""
    import re

    s = source
    for field, value in (edits or {}).items():
        if fmt == "yaml":
            pat = re.compile(r"(^\s*" + re.escape(field) + r"\s*:\s*)[-0-9.]+", re.M)
            if pat.search(s):
                s = pat.sub(lambda m: m.group(1) + str(value), s)
                continue
        key = _HELIX_CONSTRAINT_KEY.get(field)
        if key:
            pat = re.compile(r"(" + re.escape(key) + r"\s*:\s*)[-0-9.]+")
            if pat.search(s):
                s = pat.sub(lambda m: m.group(1) + str(value), s)
                continue
        if field == "max_homopolymer":
            pat = re.compile(r"homopolymer\(>=\s*\d+\s*\)")
            if pat.search(s):
                s = pat.sub(f"homopolymer(>={value})", s)
            continue
        if field == "avoid_restriction_sites" and isinstance(value, list) and fmt != "yaml":
            m = re.search(r"avoid:\s*\[([^\]]*)\]", s)
            if m:
                inner = m.group(1)
                additions = [f"restriction_site({site})" for site in value
                             if f"restriction_site({site})" not in inner]
                if additions:
                    joined = ", ".join([inner.strip().rstrip(",")] + additions) if inner.strip() else ", ".join(additions)
                    s = s[: m.start(1)] + " " + joined + " " + s[m.end(1):]
    return s


@app.post("/api/author")
def author_endpoint(req: AuthorRequest) -> dict:
    if not req.request.strip():
        raise HTTPException(status_code=400, detail={"type": "author", "message": "Describe what you want to edit."})
    client = _llm(req.model)
    try:
        source = SpecAuthor(client).draft(req.request)
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"type": "llm", "message": str(exc)})
    except SpecAuthoringError as exc:
        raise HTTPException(status_code=422, detail={"type": "author", "message": str(exc)})
    return {
        "source": source,
        "format": "helix",
        "usage": client.last_usage,
        "cost": estimate_cost(client.model, client.last_usage),
        "model": client.model,
    }


@app.post("/api/critique")
def critique_endpoint(req: CritiqueRequest) -> dict:
    spec = _parse_or_400(req.source, req.format)
    try:
        design = compile_spec(spec)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"type": "compile", "message": str(exc)})
    client = _llm(req.model)
    try:
        critique = DesignCritic(client).review(spec, design)
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"type": "llm", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"type": "critique", "message": str(exc)})
    revised = _patch_constraints_source(req.source, req.format, critique.suggested_constraint_edits)
    return {
        **critique.model_dump(mode="json"),
        "revised_source": revised if revised != req.source else None,
        "usage": client.last_usage,
        "cost": estimate_cost(client.model, client.last_usage),
        "model": client.model,
    }


@app.post("/api/resolve")
def resolve_endpoint(req: ResolveRequest) -> dict:
    """Resolve a gene symbol to an edit-window sequence from a live gene database
    (Ensembl / NCBI) — the same providers `sequence_provider:` uses in a spec."""
    from helix.adapters.registry import default_registry
    from helix.ir.spec import ExperimentSpec, SimulateSpec, TargetSpec

    spec = ExperimentSpec(
        name="resolve", genome_build=req.build,
        target=TargetSpec(gene=req.gene),
        simulate=SimulateSpec(sequence_provider=req.provider),
    )
    try:
        provider = default_registry().sequence(req.provider)
        target = provider.resolve(spec)
    except Exception as exc:  # network / not-found — surface cleanly
        raise HTTPException(status_code=502, detail={"type": "resolve", "message": str(exc)})
    return {
        "gene": target.gene, "genome_build": target.genome_build,
        "length": target.length, "source": target.source, "sequence": target.sequence,
    }


@app.get("/api/adapters")
def adapters_endpoint() -> dict:
    """The simulation backends the compiler can connect to, per role — each with its
    kind (verified / heuristic / mock / external / database / remote), whether it is
    ready, the `simulate {}` key to select it, and (for external tools) how to enable it.

    ``sim_key`` is the key to write in a spec's ``simulate {}`` block; ``prov_key`` is
    the key under a design's ``provenance.adapters`` — so the UI can mark the backend a
    given run actually used.
    """
    import importlib.util as _u

    def has(mod: str) -> bool:
        return _u.find_spec(mod) is not None

    roles = [
        {"label": "sequence provider", "sim_key": "sequence_provider", "prov_key": "sequence", "options": [
            {"key": "inline", "kind": "builtin", "note": "sequence written in the spec"},
            {"key": "ensembl", "kind": "database", "note": "Ensembl REST — live gene resolution", "configured": True},
            {"key": "ncbi", "kind": "database", "note": "NCBI E-utilities — live", "configured": True},
            {"key": "fallback", "kind": "database", "note": "Ensembl, then NCBI on failure", "configured": True},
        ]},
        {"label": "on-target efficiency", "sim_key": "on_target", "prov_key": "on_target", "options": [
            {"key": "heuristic_gc", "kind": "heuristic", "note": "transparent GC/position heuristic"},
            {"key": "rule_set_1", "kind": "verified", "note": "Doench 2014 — verified vs CRISPOR", "configured": True},
        ]},
        {"label": "off-target scan", "sim_key": "off_target", "prov_key": "off_target", "options": [
            {"key": "mock_seed", "kind": "mock", "note": "hash-derived, offline placeholder"},
            {"key": "cas_offinder_cfd", "kind": "external", "note": "real CFD (Doench 2016) + genome-wide Cas-OFFinder scan",
             "configured": bool(os.environ.get("HELIX_GENOME_DIR")),
             "setup": "export HELIX_CASOFFINDER_BIN=cas-offinder and HELIX_GENOME_DIR=/path/to/genome"},
        ]},
        {"label": "repair outcome", "sim_key": "repair_outcome", "prov_key": "repair", "options": [
            {"key": "mock_indel", "kind": "mock", "note": "hash-derived, offline placeholder"},
            {"key": "indelphi", "kind": "external", "note": "inDelphi indel spectrum (Shen 2018)",
             "configured": has("indelphi"), "setup": "pip install inDelphi-model"},
        ]},
        {"label": "base-edit outcome", "sim_key": "base_edit_model", "prov_key": "base_edit_model", "options": [
            {"key": "window_heuristic", "kind": "heuristic", "note": "editing-window heuristic"},
            {"key": "behive", "kind": "external", "note": "BE-Hive efficiency + bystander (Arbab 2020)",
             "configured": has("behive"), "setup": "install BE-Hive"},
        ]},
        {"label": "prime-edit outcome", "sim_key": "prime_edit_model", "prov_key": "prime_edit_model", "options": [
            {"key": "pe_heuristic", "kind": "heuristic", "note": "PBS/RTT heuristic"},
            {"key": "pridict", "kind": "external", "note": "PRIDICT efficiency (Mathis 2023)",
             "configured": has("pridict"), "setup": "install PRIDICT"},
        ]},
        {"label": "variant source", "sim_key": "variant_source", "prov_key": "variant", "options": [
            {"key": "none", "kind": "builtin", "note": "no variant check (default)"},
            {"key": "ensembl", "kind": "database", "note": "flag common seed/PAM SNPs (needs a resolved locus)",
             "configured": True},
        ]},
        {"label": "structure / folding", "sim_key": None, "prov_key": None, "options": [
            {"key": "esmfold", "kind": "remote", "note": "ESMFold API — real protein fold, no key", "configured": True},
            {"key": "boltz / alphafold3", "kind": "external", "note": "full Cas9-gRNA-DNA complex fold",
             "configured": bool(os.environ.get("HELIX_FOLDING_BIN")),
             "setup": "export HELIX_FOLDING_BIN=/path/to/boltz (GPU recommended)"},
        ]},
    ]
    return {"roles": roles}


@app.post("/api/fold")
def fold_endpoint(req: FoldRequest) -> dict:
    """Fold a SpCas9 domain with the real ESMFold API and return the PDB + pLDDT."""
    from helix.structure.data.spcas9 import SPCAS9_PROTEIN
    from helix.structure.esmfold import SPCAS9_DOMAINS, EsmFoldError, esmfold_pdb, mean_plddt

    lo, hi, label = SPCAS9_DOMAINS.get(req.region, SPCAS9_DOMAINS["hnh"])
    seq = SPCAS9_PROTEIN[lo:hi]
    try:
        pdb = esmfold_pdb(seq)
    except EsmFoldError as exc:
        raise HTTPException(status_code=502, detail={"type": "fold", "message": str(exc)})
    return {
        "name": f"SpCas9 {label} ({lo + 1}–{hi})",
        "region": req.region, "residues": len(seq),
        "plddt": mean_plddt(pdb), "pdb": pdb, "tool": "ESMFold",
    }


@app.get("/api/examples", response_model=List[ExampleOut])
def examples() -> List[ExampleOut]:
    out: List[ExampleOut] = []
    for path in sorted(_EXAMPLES_DIR.glob("*")):
        if path.suffix.lower() in (".hx", ".helix"):
            fmt = "helix"
        elif path.suffix.lower() in (".yaml", ".yml"):
            fmt = "yaml"
        else:
            continue
        out.append(ExampleOut(name=path.stem, format=fmt, source=path.read_text(encoding="utf-8")))
    return out


@app.post("/api/validate")
def validate(req: CompileRequest) -> dict:
    spec = _parse_or_400(req.source, req.format)
    verdict = BiosecurityScreen().screen(spec)
    return {"name": spec.name, "safety": verdict.model_dump(mode="json")}


@app.post("/api/export")
def export_endpoint(req: StructureRequest) -> dict:
    """Order-ready oligos (guides, pegRNAs, ssODN donor, primers) + IDT CSV + rough cost."""
    from helix.ir.design import ResolvedDesign
    from helix.report.oligos import cost_estimate, items_to_csv, order_items

    try:
        design = ResolvedDesign.model_validate(req.design)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"type": "export", "message": str(exc)})
    items = order_items(design)
    return {"items": [i.model_dump() for i in items], "csv": items_to_csv(items), "cost": cost_estimate(items)}


@app.post("/api/example-reads")
def example_reads_endpoint(req: StructureRequest) -> dict:
    """Synthetic amplicon reads for this design (NHEJ-like indels at the cut) — demo input."""
    from helix.analysis.amplicon import synthetic_reads
    from helix.ir.design import ResolvedDesign

    try:
        design = ResolvedDesign.model_validate(req.design)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"type": "reads", "message": str(exc)})
    if not design.target:
        raise HTTPException(status_code=400, detail={"type": "reads", "message": "design has no target sequence"})
    g = (design.selected or design.guides or [None])[0]
    n = len(design.target.sequence)
    cut = g.cut_site if g else n // 2
    cut = max(27, min(n - 27, cut))  # keep within the analyzer's anchor range so demo reads align
    mode = "sub" if design.modality in ("base_edit", "prime_edit") else "indel"
    reads = synthetic_reads(design.target.sequence, cut, mode=mode)
    return {"reads": "\n".join(reads), "count": len(reads)}


def _reconcile_ui(design, analysis) -> dict:
    """Modality-agnostic predicted-vs-observed reconciliation for the UI."""
    out = {"observed_efficiency": analysis.editing_efficiency,
           "observed_frameshift": analysis.frameshift_fraction, "notes": []}
    g = (design.selected or design.guides or [None])[0]
    if g is None:  # prime editing lists pegRNAs, not guides
        p = design.prime_edits[0] if design.prime_edits else None
        if p:
            d = round(abs(p.predicted_efficiency - analysis.editing_efficiency), 3)
            out.update(predicted_efficiency=p.predicted_efficiency, efficiency_delta=d, efficiency_agrees=d <= 0.2)
            out["notes"].append(f"pegRNA predicted efficiency {p.predicted_efficiency:.2f} vs observed "
                                f"{analysis.editing_efficiency:.2f} (Δ {d:.2f}).")
        return out
    out["predicted_on_target"] = g.on_target_score
    if g.repair and analysis.frameshift_fraction is not None:
        pf = g.repair.frameshift_fraction
        d = round(abs(pf - analysis.frameshift_fraction), 3)
        out.update(predicted_frameshift=pf, frameshift_delta=d, frameshift_agrees=d <= 0.15)
        out["notes"].append(f"frameshift predicted {pf:.2f} vs observed {analysis.frameshift_fraction:.2f} "
                            f"(Δ {d:.2f}); {'agrees' if d <= 0.15 else 'DIVERGES'}.")
    out["notes"].append(f"observed editing {analysis.editing_efficiency:.2f} over {analysis.reads_aligned} reads; "
                        f"on-target {g.on_target_score:.2f} is a relative rank, not a direct rate.")
    if analysis.editing_efficiency < 0.10:
        out["notes"].append("Low observed editing — check delivery/guide before trusting outcomes.")
    return out


@app.post("/api/analyze")
def analyze_endpoint(req: AnalyzeRequest) -> dict:
    """Quantify editing from amplicon reads and reconcile against the design's prediction."""
    from helix.analysis.amplicon import analyze_amplicon, parse_reads
    from helix.ir.design import ResolvedDesign

    try:
        design = ResolvedDesign.model_validate(req.design)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"type": "analyze", "message": str(exc)})
    ref = req.reference or (design.target.sequence if design.target else "")
    if not ref:
        raise HTTPException(status_code=400, detail={"type": "analyze", "message": "no reference amplicon (design has no target)"})
    reads = parse_reads(req.reads)
    if not reads:
        raise HTTPException(status_code=400, detail={"type": "analyze", "message": "no reads parsed — paste FASTQ/FASTA or one sequence per line"})
    g = (design.selected or design.guides or [None])[0]
    try:
        analysis, spectrum = analyze_amplicon(ref, reads, cut_pos=g.cut_site if g else None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"type": "analyze", "message": str(exc)})
    return {"analysis": analysis.model_dump(mode="json"), "spectrum": spectrum,
            "reconciliation": _reconcile_ui(design, analysis)}


@app.post("/api/structure")
def structure_endpoint(req: StructureRequest) -> dict:
    """Assemble the Cas9-gRNA-DNA complex for a design's top guide (SpCas9), and
    fold it when a backend is configured (HELIX_FOLDING_BIN); otherwise return the
    design-specific composition + AlphaFold3 input so the Complex tab reflects the
    actual guide, with the reference PDB as the visual stand-in."""
    from helix.ir.design import ResolvedDesign
    from helix.ir.enums import Enzyme
    from helix.structure.complex import build_complex, to_af3_json

    ref = {"reference_pdb": "4OO8"}
    try:
        design = ResolvedDesign.model_validate(req.design)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"type": "structure", "message": str(exc)})
    if design.resolved_enzyme is not Enzyme.SPCAS9 or design.target is None:
        return {**ref, "available": False,
                "reason": f"Structural assembly is wired for SpCas9 with a resolved target "
                          f"(this design: {design.resolved_enzyme.value})."}
    guide = (design.selected or design.guides or [None])[0]
    if guide is None:
        return {**ref, "available": False,
                "reason": "No nuclease guide to assemble (prime-edit designs list pegRNAs)."}

    cx = build_complex(guide, design.target)
    af3 = to_af3_json(cx)
    confidence, backend = None, "not configured"
    if os.environ.get("HELIX_FOLDING_BIN") or os.environ.get("HELIX_FOLDING_TOOL"):
        try:
            from helix.structure.backend import SubprocessFoldingBackend

            fb = SubprocessFoldingBackend.from_env()
            r = fb.fold(af3)
            confidence = {"ptm": r.get("ptm", 0.0), "iptm": r.get("iptm", 0.0), "plddt": r.get("plddt", 0.0)}
            backend = fb.name
        except Exception as exc:  # missing binary / fold failure — degrade cleanly
            backend = f"unavailable: {exc}"
    return {
        **ref,
        "available": True,
        "label": cx.label,
        "chains": [
            {"type": "protein", "id": "A", "name": "SpCas9", "length": len(cx.protein)},
            {"type": "rna", "id": "B", "name": "sgRNA (this guide)", "length": len(cx.guide_rna), "sequence": cx.guide_rna},
            {"type": "dna", "id": "C", "name": "target (sense)", "length": len(cx.target_dna_sense), "sequence": cx.target_dna_sense},
            {"type": "dna", "id": "D", "name": "target (antisense)", "length": len(cx.target_dna_antisense)},
        ],
        "af3_input": af3,
        "confidence": confidence,
        "backend": backend,
    }


@app.post("/api/compile")
def compile_endpoint(req: CompileRequest) -> dict:
    spec = _parse_or_400(req.source, req.format)
    try:
        design = compile_spec(spec)
    except Exception as exc:  # config/adapter errors surface as a clean 400 for the UI
        raise HTTPException(status_code=400, detail={"type": "compile", "message": str(exc)})
    return {
        "design": design.model_dump(mode="json"),
        "protocol": render_markdown(design),
    }


def _one_result(item: CompileRequest) -> dict:
    """Compile a single batch item, capturing parse/compile errors in-band."""
    try:
        spec = _parse(item.source, item.format)
    except Exception as exc:
        return {"name": None, "error": str(exc)}
    try:
        design = compile_spec(spec)
    except Exception as exc:
        return {"name": spec.name, "error": str(exc)}
    return {"name": spec.name, "design": design.model_dump(mode="json"), "protocol": render_markdown(design)}


@app.post("/api/compile-batch")
def compile_batch_endpoint(req: BatchRequest) -> dict:
    """Compile many specs independently (multiplex / pooled designs)."""
    return {"results": [_one_result(item) for item in req.items]}


@app.post("/api/runs")
def save_run(req: SaveRunRequest) -> dict:
    return _store.add(req.design, req.protocol)


@app.get("/api/runs")
def list_runs() -> dict:
    return {"runs": _store.list()}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = _store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"type": "not_found", "message": "run not found"})
    return {"design": run["design"], "protocol": run["protocol"]}


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict:
    return {"ok": _store.delete(run_id)}


@app.delete("/api/runs")
def clear_runs() -> dict:
    _store.clear()
    return {"ok": True}


@app.post("/api/compile-library")
def compile_library_endpoint(req: LibraryRequest) -> dict:
    """Expand one base spec across genes and compile each (a knockout/edit library)."""
    base = _parse_or_400(req.source, req.format)
    outcomes = compile_batch(library_specs(base, req.genes))
    return {
        "results": [
            {
                "name": o.name,
                "design": o.design.model_dump(mode="json") if o.design else None,
                "protocol": render_markdown(o.design) if o.design else None,
                "error": o.error,
            }
            for o in outcomes
        ]
    }


# Serve the built web UI from the same server when it exists, so `helix serve` runs
# the whole product on one origin. Mounted LAST so /api/* routes always win; a no-op
# when the frontend hasn't been built (the API still serves fine on its own).
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="webapp")
