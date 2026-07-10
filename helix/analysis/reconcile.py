"""Reconcile a design's predictions with observed sequencing results.

This is the loop closure: the compiler predicted a frameshift/knockout
distribution (inDelphi) and an on-target efficiency (Doench); CRISPResso2 measured
what happened. ``reconcile`` reports where they agree and where they diverge.
"""

from __future__ import annotations

from helix.analysis.models import EditingAnalysis, LoopReconciliation
from helix.ir.design import ResolvedDesign


def reconcile(
    design: ResolvedDesign,
    analysis: EditingAnalysis,
    guide_index: int = 0,
    tolerance: float = 0.15,
) -> LoopReconciliation:
    """Compare the design's top guide (by default) against observed editing."""
    if not design.selected:
        raise ValueError("design has no selected guide to reconcile against")
    guide = design.selected[guide_index]

    predicted_fs = guide.repair.frameshift_fraction
    observed_fs = analysis.frameshift_fraction
    delta = agrees = None
    notes = []

    if observed_fs is None:
        notes.append(
            "No coding frameshift measured (pass a coding sequence to CRISPResso for "
            "a frameshift comparison)."
        )
    else:
        delta = round(abs(predicted_fs - observed_fs), 4)
        agrees = delta <= tolerance
        verdict = "agrees" if agrees else "DIVERGES"
        notes.append(
            f"frameshift predicted {predicted_fs:.2f} vs observed {observed_fs:.2f} "
            f"(Δ={delta:.2f}); {verdict} at tolerance {tolerance}."
        )

    notes.append(
        f"observed editing efficiency {analysis.editing_efficiency:.2f} over "
        f"{analysis.reads_aligned} reads; on-target score {guide.on_target_score:.2f} "
        "is a relative rank, not a direct rate."
    )
    if analysis.editing_efficiency < 0.10:
        notes.append("WARNING: low observed editing — check delivery/guide before trusting outcomes.")

    return LoopReconciliation(
        guide_spacer=guide.spacer,
        predicted_frameshift=predicted_fs,
        observed_frameshift=observed_fs,
        frameshift_delta=delta,
        frameshift_agrees=agrees,
        predicted_on_target=guide.on_target_score,
        observed_editing_efficiency=analysis.editing_efficiency,
        tolerance=tolerance,
        notes=notes,
    )
