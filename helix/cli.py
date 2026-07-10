"""Helix command-line interface.

    helix author "<request>"                natural language -> Helix .hx (LLM)
    helix compile <spec> [-o OUT] [--strategy llm]   full pipeline -> bundle
    helix validate <spec>                   parse + safety screen only

Kept deliberately small; the CLI is just a front door to :mod:`helix.compiler`
and the Phase-2 agents. Agent commands need an LLM (ANTHROPIC_API_KEY) and fail
with a clear message otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from helix import __version__
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import load_spec
from helix.report.bundle import render_markdown, write_bundle
from helix.safety.screen import BiosecurityScreen


def _cmd_validate(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    verdict = BiosecurityScreen().screen(spec)
    print(f"Spec '{spec.name}' parsed OK.")
    print(f"Safety: {'ALLOWED' if verdict.allowed else 'BLOCKED'}")
    for r in verdict.reasons:
        print(f"  - {r}")
    return 0 if verdict.allowed else 2


def _cmd_compile(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)

    strategy = None
    if args.strategy in ("llm", "rag"):
        from helix.agents.llm import AnthropicClient
        from helix.agents.strategy import (
            DeterministicStrategyResolver,
            LLMStrategyResolver,
            RAGStrategyResolver,
        )

        client = AnthropicClient()
        fallback = DeterministicStrategyResolver()
        if args.strategy == "rag":
            strategy = RAGStrategyResolver(client, model_label=client.model, fallback=fallback)
        else:
            strategy = LLMStrategyResolver(client, model_label=client.model, fallback=fallback)

    design = compile_spec(spec, strategy=strategy)

    print(render_markdown(design))
    if args.strategy == "rag" and getattr(strategy, "last_citations", None):
        print("Strategy citations: " + "; ".join(strategy.last_citations))
    if args.out:
        path = write_bundle(design, args.out)
        print(f"\nBundle written to {path}/ (design.json, protocol.md)")

    if not design.safety.allowed:
        return 2
    return 0 if design.feasible else 1


def _cmd_author(args: argparse.Namespace) -> int:
    from helix.agents.authoring import SpecAuthor
    from helix.agents.llm import AnthropicClient

    source = SpecAuthor(AnthropicClient()).draft(args.request)
    print(source)
    if args.out:
        Path(args.out).write_text(source + "\n", encoding="utf-8")
        print(f"\n# written to {args.out}", file=sys.stderr)
    return 0


def _cmd_critique(args: argparse.Namespace) -> int:
    from helix.agents.critic import DesignCritic
    from helix.agents.llm import AnthropicClient

    spec = load_spec(args.spec)
    design = compile_spec(spec)
    critique = DesignCritic(AnthropicClient()).review(spec, design)

    print(f"# Critique of {design.spec_name}\n\n{critique.summary}\n")
    for f in critique.findings:
        print(f"- [{f.severity}] ({f.category}) {f.message}")
        if f.suggestion:
            print(f"    ↳ {f.suggestion}")
    if critique.suggested_constraint_edits:
        print(f"\nsuggested constraint edits: {critique.suggested_constraint_edits}")
    if critique.dropped_edits:
        print(f"(dropped invalid edits: {', '.join(critique.dropped_edits)})")
    return 0


def _cmd_refine(args: argparse.Namespace) -> int:
    from helix.agents.critic import DesignCritic
    from helix.agents.llm import AnthropicClient
    from helix.agents.refine import RefineLoop

    spec = load_spec(args.spec)
    result = RefineLoop(DesignCritic(AnthropicClient()), max_iters=args.max_iters).run(spec)

    print(f"# Autonomous refine of {spec.name}\n")
    for step in result.steps:
        verdict = "adopted" if step.adopted else "rejected (guardrail)"
        print(f"iter {step.iteration}: edits {step.applied_edits} -> "
              f"feasible={step.feasible}, {step.selected_count} selected [{verdict}]")
    print(f"\nconverged={result.converged} ({result.reason})")
    print(f"final constraints: {result.spec.constraints.model_dump()}")
    print(f"final design: feasible={result.design.feasible}, {len(result.design.selected)} guides")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("error: install the web extra — pip install 'helix-dsl[web]'", file=sys.stderr)
        return 1
    print(f"Helix API on http://{args.host}:{args.port}  (docs at /docs)")
    uvicorn.run("helix.server.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_mcp(args: argparse.Namespace) -> int:
    from helix.mcp.server import serve

    serve()  # stdio JSON-RPC loop; runs until the client closes the pipe
    return 0


def _cmd_structure(args: argparse.Namespace) -> int:
    from helix.ir.design import ResolvedDesign
    from helix.structure import StructureAnalyzer, SubprocessFoldingBackend

    design = ResolvedDesign.model_validate_json(Path(args.design).read_text())
    if not design.selected or design.target is None:
        print("error: no selected guide to fold (structure supports KO/base-edit designs)",
              file=sys.stderr)
        return 1
    assessment = StructureAnalyzer(SubprocessFoldingBackend.from_env()).assess(
        design.selected[0], design.target, flank=args.flank
    )
    c = assessment.confidence
    print(f"# Structure of {assessment.label}  (backend: {assessment.backend})\n")
    print(f"pTM {c.ptm:.2f}  ·  ipTM {c.iptm:.2f}  ·  pLDDT {c.plddt:.1f}")
    print(f"well-formed: {assessment.well_formed}")
    for note in assessment.notes:
        print(f"- {note}")
    if assessment.structure_path:
        print(f"structure: {assessment.structure_path}")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    from helix.analysis import Crispresso2Backend, CrispressoAnalyzer, reconcile
    from helix.ir.design import ResolvedDesign

    design = ResolvedDesign.model_validate_json(Path(args.design).read_text())
    amplicon = args.amplicon or (design.target.sequence if design.target else None)
    if not amplicon:
        print("error: no amplicon; pass --amplicon", file=sys.stderr)
        return 1

    analyzer = CrispressoAnalyzer(Crispresso2Backend.from_env())
    analysis = analyzer.analyze(amplicon, args.reads, coding_seq=args.coding)
    result = reconcile(design, analysis)

    print(f"# Analysis of {design.spec_name}\n")
    print(f"observed editing: {analysis.editing_efficiency:.2%} "
          f"({analysis.modified_reads}/{analysis.reads_aligned} reads)")
    if analysis.frameshift_fraction is not None:
        print(f"observed frameshift: {analysis.frameshift_fraction:.2%}")
    print("\n## Predicted vs observed")
    for note in result.notes:
        print(f"- {note}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="helix", description=__doc__)
    parser.add_argument("--version", action="version", version=f"helix {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="parse a spec and run the safety screen")
    v.add_argument("spec", type=Path)
    v.set_defaults(func=_cmd_validate)

    c = sub.add_parser("compile", help="compile a spec into a design bundle")
    c.add_argument("spec", type=Path)
    c.add_argument("-o", "--out", type=Path, help="write design.json + protocol.md here")
    c.add_argument(
        "--strategy",
        choices=["deterministic", "llm", "rag"],
        default="deterministic",
        help="how to resolve `enzyme: auto` (deterministic | llm | rag)",
    )
    c.set_defaults(func=_cmd_compile)

    a = sub.add_parser("author", help="draft a Helix spec from natural language (LLM)")
    a.add_argument("request", help="plain-English description of the edit")
    a.add_argument("-o", "--out", type=Path, help="also write the .hx source here")
    a.set_defaults(func=_cmd_author)

    cr = sub.add_parser("critique", help="compile a spec and adversarially review it (LLM)")
    cr.add_argument("spec", type=Path)
    cr.set_defaults(func=_cmd_critique)

    rf = sub.add_parser("refine", help="autonomously critique+recompile until convergence (LLM)")
    rf.add_argument("spec", type=Path)
    rf.add_argument("--max-iters", type=int, default=5)
    rf.set_defaults(func=_cmd_refine)

    sv = sub.add_parser("serve", help="run the Helix HTTP API (needs the web extra)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true")
    sv.set_defaults(func=_cmd_serve)

    mc = sub.add_parser("mcp", help="run Helix as an MCP server over stdio (for AI agents)")
    mc.set_defaults(func=_cmd_mcp)

    st = sub.add_parser("structure", help="fold the Cas9-gRNA-DNA complex of a design's top guide")
    st.add_argument("design", type=Path, help="a design.json from `compile -o`")
    st.add_argument("--flank", type=int, default=10, help="nt of DNA flank each side of the protospacer")
    st.set_defaults(func=_cmd_structure)

    an = sub.add_parser("analyze", help="analyse amplicon reads and reconcile with a design")
    an.add_argument("design", type=Path, help="a design.json from `compile -o`")
    an.add_argument("--reads", required=True, help="FASTQ of amplicon reads")
    an.add_argument("--amplicon", help="amplicon reference (defaults to the design's target window)")
    an.add_argument("--coding", help="coding sequence, to measure frameshift")
    an.set_defaults(func=_cmd_analyze)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # surface clean errors to the terminal
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
