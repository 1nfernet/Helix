"""Emit the design as (1) a canonical JSON artifact and (2) a human-readable
Markdown protocol. The JSON is the reproducible record; the Markdown is what a
bench scientist reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from helix.ir.design import ResolvedDesign


def render_markdown(design: ResolvedDesign) -> str:
    d = design
    lines = [f"# Helix design — {d.spec_name}", ""]

    lines += ["## Safety", ""]
    lines.append(f"- Verdict: {'ALLOWED' if d.safety.allowed else 'BLOCKED'}")
    for r in d.safety.reasons:
        lines.append(f"- {r}")
    lines.append("")

    if not d.safety.allowed:
        lines.append("_Run halted by the biosecurity screen; no guides designed._")
        return "\n".join(lines)

    t = d.target
    lines += [
        "## Target",
        "",
        f"- Gene: {t.gene}  ·  Build: {t.genome_build}  ·  Window: {t.length} nt",
        f"- Enzyme: {d.resolved_enzyme.value}",
        f"- Feasible: {d.feasible}",
        "",
    ]
    for note in d.infeasibility_notes:
        lines.append(f"> {note}")
    if d.infeasibility_notes:
        lines.append("")

    if d.modality == "prime_edit":
        lines += ["## pegRNA candidates", ""]
        pegs = [p for p in d.prime_edits if p.passed][: max(1, len(d.prime_edits))]
        if pegs:
            lines.append("| # | spacer (5'->3') | PAM | edit | PBS | RTT | on-target |")
            lines.append("|---|---|---|---|---|---|---|")
            for i, p in enumerate(pegs, 1):
                lines.append(
                    f"| {i} | `{p.spacer}` | {p.pam} | {p.edit} | `{p.pbs}` | `{p.rtt}` "
                    f"| {p.on_target_score:.2f} |"
                )
        else:
            lines.append("_No pegRNA satisfied all constraints._")
        lines.append("")
    else:
        label, outcome_col = {
            "base_edit": ("base-edit guides", "edit (window)"),
            "hdr": ("knock-in guides", "cut→edit"),
            "deletion": ("flanking guides", "cut site"),
            "crispri": ("CRISPRi guides", "TSS offset"),
            "crispra": ("CRISPRa guides", "TSS offset"),
        }.get(d.modality, ("guides", "frameshift"))
        lines += [f"## Selected {label}", ""]
        if d.selected:
            lines.append(f"| # | spacer (5'->3') | PAM | strand | on-target | max CFD | {outcome_col} | composite |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for i, g in enumerate(d.selected, 1):
                if g.base_edit:
                    be = g.base_edit
                    outcome = f"{be.window}→{be.edited_product} (+{be.bystander_count} bys)"
                elif g.hdr:
                    outcome = f"{g.hdr.cut_to_edit_distance} bp"
                elif g.regulation:
                    outcome = f"{g.regulation.tss_offset:+d} bp"
                elif d.modality == "deletion":
                    outcome = f"cut @ {g.cut_site}"
                else:
                    outcome = f"{g.repair.frameshift_fraction:.2f}" if g.repair else "-"
                lines.append(
                    f"| {i} | `{g.spacer}` | {g.pam} | {g.strand.value} | "
                    f"{g.on_target_score:.2f} | {g.off_target.max_cfd:.2f} | "
                    f"{outcome} | {g.composite_score:.3f} |"
                )
        else:
            lines.append("_No guide satisfied all constraints._")
        lines.append("")

        if d.modality == "hdr" and d.selected and d.selected[0].hdr:
            h = d.selected[0].hdr
            lines += [
                f"## Donor ({h.donor_type})",
                "",
                f"- Edit: {h.edit}  ·  cut→edit: {h.cut_to_edit_distance} bp  ·  arms: {h.arm_length} nt  ·  strand: {h.strand}",
                f"- Re-cutting: {'blocked' if h.pam_disrupted else 'NOT blocked'} — {h.recut_note}",
                f"- Sequence (5'->3'): `{h.left_arm}`**`{h.insert or '∅'}`**`{h.right_arm}`",
                "",
            ]

        if d.modality == "deletion" and d.deletion:
            p = d.deletion
            lines += [
                "## Deletion",
                "",
                f"- Span {p.requested_span} → cuts {p.left_cut}..{p.right_cut}  ·  {p.deletion_size} bp removed",
                f"- Junction (5'->3'): `{p.junction}`",
                "",
            ]

    if d.validation_primers and d.validation_primers.forward:
        p = d.validation_primers
        lines += [
            "## Validation (amplicon-seq)",
            "",
            f"- Forward: `{p.forward}`",
            f"- Reverse: `{p.reverse}`",
            f"- Amplicon: {p.amplicon_length} bp — {p.note}",
            "",
        ]

    if d.delivery:
        dv = d.delivery
        lines += ["## Delivery", ""]
        lines.append(f"- Recommended: **{dv.recommended}**  ·  cargo ~{dv.cargo_kb} kb  ·  {dv.context}")
        if dv.requested and dv.requested != dv.recommended:
            lines.append(f"- Requested: {dv.requested} ({'suitable' if dv.requested_suitable else 'see warnings'})")
        for opt in dv.options:
            warn = f" — {'; '.join(opt.warnings)}" if opt.warnings else ""
            lines.append(f"  - {opt.method}: {opt.score:.2f}{warn}")
        for note in dv.notes:
            lines.append(f"- {note}")
        lines.append("")

    prov = d.provenance
    lines += [
        "## Provenance",
        "",
        f"- Helix {prov.helix_version}  ·  {prov.timestamp_utc}",
        f"- Adapters: {', '.join(f'{k}={v}' for k, v in prov.adapters.items())}",
        "",
    ]
    return "\n".join(lines)


def write_bundle(design: ResolvedDesign, outdir: Union[str, Path]) -> Path:
    """Write ``design.json`` and ``protocol.md`` into ``outdir``; return the path."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "design.json").write_text(
        design.model_dump_json(indent=2), encoding="utf-8"
    )
    (out / "protocol.md").write_text(render_markdown(design), encoding="utf-8")
    return out
