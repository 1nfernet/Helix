"""Dual-cut deletion designer — excise a region between two flanking cuts.

Two guides are chosen so their cuts bracket the requested span: one near the 5'
boundary, one near the 3' boundary. The realized deletion is the interval between
the two cut sites; the junction is the sequence the cell rejoins by NHEJ.

Guide enumeration and scoring reuse the knockout machinery; selection is the
pairing step unique to this modality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from helix.adapters.base import OffTargetScorer, OnTargetScorer
from helix.compiler.constraints import _check_guide
from helix.compiler.guide_designer import enumerate_scored
from helix.ir.design import DeletionPlan, GuideCandidate, ResolvedTarget
from helix.ir.enums import Enzyme
from helix.ir.spec import Constraints

_MAX_BOUNDARY = 30  # bp; a cut must land within this of the requested boundary
_FLANK = 10  # bp of context shown each side of the junction


@dataclass
class DeletionResult:
    ranked: List[GuideCandidate]
    selected: List[GuideCandidate]
    plan: Optional[DeletionPlan]
    feasible: bool
    notes: List[str] = field(default_factory=list)


def _parse_span(span: str, length: int):
    lo_s, _, hi_s = span.partition("..")
    try:
        lo1, hi1 = int(lo_s), int(hi_s)
    except ValueError:
        raise ValueError(f"delete span must look like '40..90', got {span!r}")
    lo, hi = lo1 - 1, hi1  # 1-based inclusive -> 0-based [lo, hi)
    return max(0, min(lo, length)), max(0, min(hi, length))


def _nearest(guides: List[GuideCandidate], boundary: int) -> Optional[GuideCandidate]:
    pool = [g for g in guides if abs(g.cut_site - boundary) <= _MAX_BOUNDARY]
    if not pool:
        return None
    return sorted(pool, key=lambda g: (abs(g.cut_site - boundary), -g.composite_score))[0]


def design_deletion(
    target: ResolvedTarget,
    enzyme: Enzyme,
    span: str,
    on_target: OnTargetScorer,
    off_target: OffTargetScorer,
    constraints: Constraints,
) -> DeletionResult:
    length = len(target.sequence)
    lo, hi = _parse_span(span, length)

    ranked = sorted(enumerate_scored(target, enzyme, on_target, off_target),
                    key=lambda g: (-g.composite_score, g.spacer))
    for rank, g in enumerate(ranked, start=1):
        g.rank = rank
        g.checks = _check_guide(g, constraints)
        g.passed = all(c.passed for c in g.checks)
    passing = [g for g in ranked if g.passed]

    left = _nearest(passing, lo)
    right = _nearest(passing, hi)
    notes: List[str] = []
    feasible = left is not None and right is not None and right.cut_site > left.cut_site

    if feasible:
        seq = target.sequence
        junction = seq[max(0, left.cut_site - _FLANK):left.cut_site] + " / " + seq[right.cut_site:right.cut_site + _FLANK]
        plan = DeletionPlan(
            requested_span=span,
            deletion_start=left.cut_site, deletion_end=right.cut_site,
            deletion_size=right.cut_site - left.cut_site, junction=junction,
            left_cut=left.cut_site, right_cut=right.cut_site,
        )
        return DeletionResult(ranked=ranked, selected=[left, right], plan=plan, feasible=True)

    if left is None:
        notes.append(f"No passing guide cuts within {_MAX_BOUNDARY} bp of the 5' boundary.")
    if right is None:
        notes.append(f"No passing guide cuts within {_MAX_BOUNDARY} bp of the 3' boundary.")
    if left is not None and right is not None and right.cut_site <= left.cut_site:
        notes.append("Flanking cuts do not bracket a positive-length region — widen the span.")
    selected = [g for g in (left, right) if g is not None]
    return DeletionResult(ranked=ranked, selected=selected, plan=None, feasible=False, notes=notes)
