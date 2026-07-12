"""Constraint solving: check every guide, then select the best feasible set.

This is where the DSL's declarative constraints pay off. Rather than returning
"the top N guides", the compiler returns the top N guides that *satisfy every
hard constraint*, and reports infeasibility explicitly when it cannot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from helix.bio import contains_restriction_site, gc_content, max_homopolymer_run, self_complementarity
from helix.ir.design import ConstraintCheck, GuideCandidate, PrimeEditCandidate
from helix.ir.spec import Constraints


def _quality_checks(spacer: str, gc: float, c: Constraints):
    """GC-window + hairpin (self-complementarity) checks; only when configured.

    Returns (checks, self_complementarity). These are opt-in guide-quality filters —
    absent constraints add no checks, so behaviour is unchanged unless requested.
    """
    checks = []
    sc = self_complementarity(spacer)
    if c.gc_min is not None:
        checks.append(ConstraintCheck(name="gc_min", passed=gc >= c.gc_min, detail=f"{gc:.2f} vs >= {c.gc_min}"))
    if c.gc_max is not None:
        checks.append(ConstraintCheck(name="gc_max", passed=gc <= c.gc_max, detail=f"{gc:.2f} vs <= {c.gc_max}"))
    if c.max_self_complementarity is not None:
        checks.append(ConstraintCheck(
            name="max_self_complementarity", passed=sc < c.max_self_complementarity,
            detail=f"stem {sc} vs < {c.max_self_complementarity}"))
    return checks, sc


@dataclass
class SelectionResult:
    ranked: List[GuideCandidate]
    selected: List[GuideCandidate]
    feasible: bool
    notes: List[str]


def _check_guide(guide: GuideCandidate, c: Constraints) -> List[ConstraintCheck]:
    checks = [
        ConstraintCheck(
            name="on_target_min_efficiency",
            passed=guide.on_target_score >= c.on_target_min_efficiency,
            detail=f"{guide.on_target_score:.3f} vs >= {c.on_target_min_efficiency}",
        ),
        ConstraintCheck(
            name="off_target_max_cfd",
            passed=guide.off_target.max_cfd <= c.off_target_max_cfd,
            detail=f"{guide.off_target.max_cfd:.3f} vs <= {c.off_target_max_cfd}",
        ),
        ConstraintCheck(
            name="max_homopolymer",
            passed=max_homopolymer_run(guide.spacer) < c.max_homopolymer,
            detail=f"run {max_homopolymer_run(guide.spacer)} vs < {c.max_homopolymer}",
        ),
    ]
    quality, sc = _quality_checks(guide.spacer, guide.gc_content, c)
    guide.self_complementarity = sc
    checks += quality
    if c.max_variant_freq is not None:
        common = [h for h in guide.variant_hits
                  if h.region in ("seed", "PAM") and h.frequency is not None and h.frequency >= c.max_variant_freq]
        checks.append(ConstraintCheck(
            name="common_variant", passed=not common,
            detail=(f"{len(common)} common variant(s) in seed/PAM" if common else "none")))
    for enzyme in c.avoid_restriction_sites:
        hit = contains_restriction_site(guide.spacer, enzyme)
        checks.append(
            ConstraintCheck(
                name=f"avoid_{enzyme}",
                passed=not hit,
                detail="present" if hit else "absent",
            )
        )
    return checks


def evaluate_and_select(
    guides: List[GuideCandidate], constraints: Constraints
) -> SelectionResult:
    # Rank all candidates by composite score (stable, deterministic tie-break by
    # spacer so runs are byte-reproducible).
    ranked = sorted(guides, key=lambda g: (-g.composite_score, g.spacer))
    for rank, guide in enumerate(ranked, start=1):
        guide.rank = rank
        guide.checks = _check_guide(guide, constraints)
        guide.passed = all(c.passed for c in guide.checks)

    passing = [g for g in ranked if g.passed]
    selected = passing[: constraints.guides_count]

    feasible = len(selected) >= constraints.guides_count
    notes: List[str] = []
    if not feasible:
        notes.append(
            f"Requested {constraints.guides_count} guides but only {len(passing)} "
            "satisfy all constraints."
        )
        notes.extend(_suggest_relaxations(ranked, constraints))
    return SelectionResult(ranked=ranked, selected=selected, feasible=feasible, notes=notes)


def _check_spacer(spacer: str, on_target_score: float, c: Constraints) -> List[ConstraintCheck]:
    """Spacer-level checks shared by nuclease and pegRNA guides (no CFD)."""
    checks = [
        ConstraintCheck(
            name="on_target_min_efficiency",
            passed=on_target_score >= c.on_target_min_efficiency,
            detail=f"{on_target_score:.3f} vs >= {c.on_target_min_efficiency}",
        ),
        ConstraintCheck(
            name="max_homopolymer",
            passed=max_homopolymer_run(spacer) < c.max_homopolymer,
            detail=f"run {max_homopolymer_run(spacer)} vs < {c.max_homopolymer}",
        ),
    ]
    checks += _quality_checks(spacer, gc_content(spacer), c)[0]
    for enzyme in c.avoid_restriction_sites:
        checks.append(
            ConstraintCheck(
                name=f"avoid_{enzyme}",
                passed=not contains_restriction_site(spacer, enzyme),
                detail="present" if contains_restriction_site(spacer, enzyme) else "absent",
            )
        )
    return checks


def evaluate_and_select_prime(
    prime_edits: List[PrimeEditCandidate], constraints: Constraints
) -> SelectionResult:
    """Rank and select pegRNA candidates (off-target CFD not applied to nicks)."""
    ranked = sorted(prime_edits, key=lambda g: (-g.composite_score, g.spacer))
    for rank, peg in enumerate(ranked, start=1):
        peg.rank = rank
        peg.checks = _check_spacer(peg.spacer, peg.on_target_score, constraints)
        peg.passed = all(c.passed for c in peg.checks)
    passing = [p for p in ranked if p.passed]
    selected = passing[: constraints.guides_count]
    feasible = len(selected) >= constraints.guides_count
    notes = []
    if not feasible:
        notes.append(
            f"Requested {constraints.guides_count} pegRNAs but only {len(passing)} "
            "satisfy all constraints."
        )
    return SelectionResult(ranked=ranked, selected=selected, feasible=feasible, notes=notes)


def _suggest_relaxations(ranked: List[GuideCandidate], c: Constraints) -> List[str]:
    """Name the constraint that most often blocked otherwise-good guides."""
    from collections import Counter

    blockers: Counter = Counter()
    for g in ranked:
        for check in g.checks:
            if not check.passed:
                blockers[check.name] += 1
    if not blockers:
        return []
    top, count = blockers.most_common(1)[0]
    return [f"Most common blocker: '{top}' ({count} guides). Consider relaxing it."]
