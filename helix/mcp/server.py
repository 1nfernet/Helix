"""Helix as an MCP server (stdio, JSON-RPC 2.0, zero-dependency).

Exposes the deterministic Helix compiler to any MCP-capable agent — but *only*
through the spec → compile boundary. An agent proposes a reviewable Helix spec;
the tested compiler produces the verified, provenance-stamped design. The agent
never bypasses the compiler, so the same trust boundary that makes Helix auditable
for humans holds for agents.

Transport: newline-delimited JSON-RPC 2.0 over stdio (the MCP stdio transport).
`build_response` is a pure function (message dict → response dict or None) so the
whole protocol surface is unit-testable without spawning a client.

Run it with:  python -m helix.mcp   (or `helix mcp`)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from helix import __version__
from helix.adapters.registry import default_registry
from helix.compiler.pipeline import compile_spec
from helix.frontend.errors import SpecError, parse_source
from helix.ir.spec import ExperimentSpec, SimulateSpec, TargetSpec

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "helix", "version": __version__}

_REPO = Path(__file__).resolve().parents[2]
_GRAMMAR = Path(__file__).resolve().parents[1] / "frontend" / "helix_lang" / "GRAMMAR.md"
_EXAMPLES = _REPO / "examples"
_REFERENCE_EXAMPLES = ["tp53_ko.hx", "istop_base_edit.hx", "hdr_silent_pamblock.hx", "tp53_prime_edit.hx"]

_AUTHORING_GUIDE = """\
# Writing a Helix spec (for agents)

Helix compiles a small declarative spec into a ranked, safety-screened, \
provenance-stamped gene-editing design. You (the agent) write or edit the spec; \
the deterministic compiler produces the design — you never call raw tools directly.

## Workflow
1. Write a `.hx` spec (grammar below; copy an example and adapt it).
2. Call `helix_compile` with it.
3. Read `feasible`, `safety.allowed`, and `infeasibility_notes` in the result. If \
infeasible or unsafe, loosen constraints or change strategy and recompile.
4. Use `top_guides` (with on/off-target scores and protein `consequence`) to choose.

## Two ways to give a target
- **Offline / deterministic**: put an inline `sequence: "ACGT…"` in the target and \
`simulate { sequence_provider: inline }`. No network needed.
- **Real coordinates**: omit the sequence, keep `gene(SYMBOL)`, and set \
`simulate { sequence_provider: ensembl }` (or `ncbi`). Or call `helix_resolve_gene` \
first to fetch a window, then paste it inline.

## Coding edits
Add `target { frame: 0 }` (codon phase of window position 0) to get a protein \
`consequence` on each guide — silent / missense / premature-STOP (a base-edit iSTOP \
knockout) — and a guaranteed-synonymous PAM-block for HDR.

Call `helix_list_models` to see which scoring/prediction backends are available.
"""

# --------------------------------------------------------------------------- #
# Tool definitions
# --------------------------------------------------------------------------- #

TOOLS = [
    {
        "name": "helix_reference",
        "description": (
            "Return the Helix DSL grammar, an authoring guide, and worked example specs. "
            "Call this FIRST so you know how to write a valid spec before compiling."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "helix_compile",
        "description": (
            "Compile a Helix spec into a ranked, safety-screened gene-editing design. "
            "This is the core tool: the deterministic compiler turns your spec into guides, "
            "delivery, primers, safety verdict, feasibility, and provenance. Returns a clean "
            "error (with line/col for syntax) if the spec is invalid."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "The Helix (.hx) or YAML spec text."},
                "format": {"type": "string", "enum": ["helix", "yaml"], "default": "helix"},
                "full": {
                    "type": "boolean",
                    "default": False,
                    "description": "Return the full design JSON instead of a summary.",
                },
            },
            "required": ["source"],
            "additionalProperties": False,
        },
    },
    {
        "name": "helix_resolve_gene",
        "description": (
            "Resolve a gene symbol to an edit-window DNA sequence and genomic coordinates via "
            "a live database (Ensembl/NCBI). Needs network access. Use the returned sequence "
            "inline in a spec, or the locus for variant-aware design."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol, e.g. TP53."},
                "genome_build": {"type": "string", "default": "GRCh38"},
                "database": {"type": "string", "enum": ["ensembl", "ncbi", "fallback"], "default": "ensembl"},
            },
            "required": ["gene"],
            "additionalProperties": False,
        },
    },
    {
        "name": "helix_list_models",
        "description": (
            "List the simulation/computation backends registered for each role "
            "(sequence, on-/off-target, repair, base-/prime-edit, variants) — the selectable "
            "`simulate {}` options. External ones (Cas-OFFinder, inDelphi, BE-Hive, PRIDICT) "
            "activate only when their binary/package is installed on the backend."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


# --------------------------------------------------------------------------- #
# Tool handlers  (return a str, or an object that gets JSON-encoded)
# --------------------------------------------------------------------------- #

def _read_grammar() -> str:
    """Read GRAMMAR.md — via package resources when installed, else the repo path."""
    try:
        import importlib.resources as ir

        return ir.files("helix.frontend.helix_lang").joinpath("GRAMMAR.md").read_text(encoding="utf-8")
    except Exception:
        try:
            return _GRAMMAR.read_text(encoding="utf-8")
        except OSError:
            return ""


def _tool_reference(_args: dict):
    parts = [_AUTHORING_GUIDE]
    grammar = _read_grammar()
    if grammar:
        parts.append("\n\n---\n\n" + grammar)
    # Bonus example specs when running from a checkout (the grammar already carries one).
    examples = [f"\n## {n}\n```hx\n{(_EXAMPLES / n).read_text(encoding='utf-8').strip()}\n```\n"
                for n in _REFERENCE_EXAMPLES if (_EXAMPLES / n).exists()]
    if examples:
        parts.append("\n\n---\n\n# Example specs\n" + "".join(examples))
    return "".join(parts)


def _tool_compile(args: dict):
    source = args.get("source")
    if not isinstance(source, str) or not source.strip():
        raise _ToolError("`source` (the spec text) is required.")
    fmt = args.get("format", "helix")
    spec = parse_source(source, fmt)  # raises SpecError with a clean message
    design = compile_spec(spec, registry=default_registry())
    return _design_summary(design, full=bool(args.get("full")))


def _tool_resolve_gene(args: dict):
    gene = args.get("gene")
    if not isinstance(gene, str) or not gene.strip():
        raise _ToolError("`gene` is required.")
    build = args.get("genome_build", "GRCh38")
    db = args.get("database", "ensembl")
    spec = ExperimentSpec(
        name="resolve",
        genome_build=build,
        target=TargetSpec(gene=gene),
        simulate=SimulateSpec(sequence_provider=db),
    )
    provider = default_registry().sequence(db)
    try:
        target = provider.resolve(spec)
    except Exception as exc:  # network / not-found — report cleanly, not a crash
        raise _ToolError(f"Could not resolve {gene!r} via {db}: {exc}")
    return {
        "gene": target.gene,
        "genome_build": target.genome_build,
        "length": target.length,
        "source": target.source,
        "locus": target.locus.model_dump() if target.locus else None,
        "sequence": target.sequence,
    }


def _tool_list_models(_args: dict):
    return {
        "roles": default_registry().catalog(),
        "note": (
            "Select a backend in the spec's simulate {} block by key. Built-ins run offline; "
            "external tools (cas_offinder_cfd, indelphi, behive, pridict, ensembl, ncbi) need "
            "their binary/package/network on the backend or the compiler falls back to a heuristic."
        ),
    }


HANDLERS = {
    "helix_reference": _tool_reference,
    "helix_compile": _tool_compile,
    "helix_resolve_gene": _tool_resolve_gene,
    "helix_list_models": _tool_list_models,
}


class _ToolError(Exception):
    """A tool-level error surfaced to the agent as an isError result."""


def _design_summary(d, full: bool = False) -> dict:
    if full:
        return d.model_dump(mode="json")
    prime = d.modality == "prime_edit"
    pool = d.prime_edits if prime else d.guides
    top = sorted(pool, key=lambda g: (g.rank if g.rank is not None else 999))[:5]
    guides = []
    for g in top:
        if prime:
            gg = {"rank": g.rank, "spacer": g.spacer, "strand": g.strand.value,
                  "edit": g.edit, "efficiency": round(g.predicted_efficiency, 3), "passed": g.passed}
            if g.consequence:
                gg["consequence"] = g.consequence.label
        else:
            gg = {"rank": g.rank, "spacer": g.spacer, "pam": g.pam, "strand": g.strand.value,
                  "gc": round(g.gc_content, 2), "on_target": round(g.on_target_score, 3),
                  "off_target_cfd": round(g.off_target.max_cfd, 3),
                  "composite": round(g.composite_score, 4), "passed": g.passed}
            cons = (g.base_edit.consequence if g.base_edit and g.base_edit.consequence
                    else g.hdr.consequence if g.hdr and g.hdr.consequence else None)
            if cons:
                gg["consequence"] = cons.label
            if g.hdr:
                gg["cut_to_edit_bp"] = g.hdr.cut_to_edit_distance
                gg["silent_pam_block"] = g.hdr.silent_pam_block
            if g.repair:
                gg["frameshift"] = round(g.repair.frameshift_fraction, 3)
            if g.regulation:
                gg["tss_offset"] = g.regulation.tss_offset
        guides.append(gg)
    out = {
        "spec_name": d.spec_name,
        "modality": d.modality,
        "enzyme": d.resolved_enzyme.value,
        "feasible": d.feasible,
        "safety": {"allowed": d.safety.allowed, "reasons": d.safety.reasons},
        "candidate_count": len(pool),
        "selected_count": sum(1 for g in pool if g.passed),
        "top_guides": guides,
        "infeasibility_notes": d.infeasibility_notes,
        "provenance": {"helix_version": d.provenance.helix_version, "adapters": d.provenance.adapters},
    }
    if d.target:
        out["target"] = {
            "gene": d.target.gene, "genome_build": d.target.genome_build,
            "length": d.target.length, "source": d.target.source,
            "locus": d.target.locus.model_dump() if d.target.locus else None,
        }
    if d.deletion:  # the defining output of the dual-cut deletion modality
        out["deletion"] = {
            "requested_span": d.deletion.requested_span,
            "deletion_size": d.deletion.deletion_size,
            "deletion_start": d.deletion.deletion_start,
            "deletion_end": d.deletion.deletion_end,
            "junction": d.deletion.junction,
            "left_cut": d.deletion.left_cut,
            "right_cut": d.deletion.right_cut,
        }
    if d.delivery:
        out["delivery"] = {"recommended": d.delivery.recommended,
                           "cargo_kb": d.delivery.cargo_kb, "notes": d.delivery.notes}
    if d.validation_primers:
        p = d.validation_primers
        out["validation_primers"] = {"forward": p.forward, "reverse": p.reverse,
                                      "amplicon_length": p.amplicon_length}
    return out


# --------------------------------------------------------------------------- #
# JSON-RPC / MCP protocol
# --------------------------------------------------------------------------- #

def _ok(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _err(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _text_content(payload) -> dict:
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, default=str)
    return {"content": [{"type": "text", "text": text}]}


def _call_tool(params: dict) -> dict:
    name = params.get("name")
    args = params.get("arguments") or {}
    handler = HANDLERS.get(name)
    if handler is None:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name!r}"}], "isError": True}
    try:
        return _text_content(handler(args))
    except (SpecError, _ToolError, ValueError, KeyError) as exc:
        # Author/spec errors — including the ValueError/KeyError the compiler raises for a
        # missing editor/donor/edit or an unknown adapter key — go back to the agent as an
        # isError "Error:" it can fix, never a raw dump or a "server bug"-looking message.
        if isinstance(exc, KeyError) and exc.args:
            msg = str(exc.args[0])  # KeyError str() adds spurious quotes
        else:
            msg = getattr(exc, "message", str(exc))
        if getattr(exc, "kind", None) == "syntax" and getattr(exc, "line", None) is not None:
            msg = f"{msg} (line {exc.line}, col {exc.col})"
        return {"content": [{"type": "text", "text": f"Error: {msg}"}], "isError": True}
    except Exception as exc:  # pragma: no cover - truly unexpected
        return {"content": [{"type": "text", "text": f"Internal error: {exc}"}], "isError": True}


def build_response(msg: dict) -> Optional[dict]:
    """Handle one JSON-RPC message; return a response dict, or None for notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _err(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
    # A JSON-RPC notification (no "id") NEVER gets a response — regardless of method.
    if "id" not in msg:
        return None
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        client_version = (msg.get("params") or {}).get("protocolVersion")
        return _ok(msg_id, {
            "protocolVersion": client_version or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return _ok(msg_id, {})
    if method == "tools/list":
        return _ok(msg_id, {"tools": TOOLS})
    if method == "tools/call":
        return _ok(msg_id, _call_tool(msg.get("params") or {}))
    if method == "resources/list":
        return _ok(msg_id, {"resources": []})
    if method == "prompts/list":
        return _ok(msg_id, {"prompts": []})
    return _err(msg_id, -32601, f"Method not found: {method}")


def serve(stdin=None, stdout=None) -> None:
    """Run the stdio JSON-RPC loop until EOF."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _write(stdout, _err(None, -32700, "Parse error"))
            continue
        response = build_response(msg)
        if response is not None:
            _write(stdout, response)


def _write(stdout, obj: dict) -> None:
    stdout.write(json.dumps(obj) + "\n")
    stdout.flush()
