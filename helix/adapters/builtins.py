"""Built-in adapters for the offline MVP.

These are honest placeholders: deterministic, transparent, and clearly labelled
as heuristics/mocks. They exist so the *architecture* runs end-to-end today. Each
one is a drop-in target for a real tool that satisfies the same Protocol:

* ``InlineSequenceProvider``  -> Ensembl/NCBI coordinate resolver
* ``HeuristicOnTargetScorer`` -> Rule Set 2 / Azimuth / DeepSpCas9
* ``MockOffTargetScorer``     -> Cas-OFFinder + CFD
* ``MockRepairOutcomePredictor`` -> inDelphi / FORECasT / Lindel

Determinism note: mocks derive their numbers from a hash of the spacer, never
from wall-clock or RNG, so runs are reproducible.
"""

from __future__ import annotations

import hashlib

from helix.bio import gc_content, normalize
from helix.ir.design import (
    OffTargetReport,
    OffTargetSite,
    RepairOutcome,
    ResolvedTarget,
)
from helix.ir.spec import ExperimentSpec


def _unit_hash(text: str, salt: str = "") -> float:
    """Deterministic pseudo-value in [0, 1) from a string."""
    digest = hashlib.sha256((salt + text).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


class InlineSequenceProvider:
    """Serve the target sequence carried inline in the spec.

    Real deployments swap this for a provider that resolves ``gene`` + ``region``
    into an edit window via Ensembl REST / NCBI E-utilities against a pinned
    genome build.
    """

    name = "inline"
    version = "0.1.0"

    def resolve(self, spec: ExperimentSpec) -> ResolvedTarget:
        seq = spec.target.sequence
        if not seq:
            raise ValueError(
                f"Target '{spec.target.gene}' has no inline sequence. The MVP "
                "requires target.sequence; a coordinate-based provider is Phase 3."
            )
        seq = normalize(seq)
        return ResolvedTarget(
            gene=spec.target.gene,
            genome_build=spec.genome_build,
            sequence=seq,
            length=len(seq),
            source=f"{self.name}@{self.version}",
        )


class HeuristicOnTargetScorer:
    """Transparent GC/position heuristic for on-target efficiency.

    NOT a validated efficiency model — a smooth, explainable stand-in so the
    pipeline produces sensible rankings offline. Favours moderate GC (~40-60%)
    and a G at the PAM-proximal position; penalises extreme GC.
    """

    name = "heuristic_gc"
    version = "0.1.0"

    def score(self, spacer: str, context: str) -> float:
        spacer = normalize(spacer)
        if not spacer:
            return 0.0
        gc = gc_content(spacer)
        # Triangular preference peaking at GC == 0.55.
        gc_term = 1.0 - abs(gc - 0.55) / 0.55
        gc_term = max(0.0, min(1.0, gc_term))
        # PAM-proximal G is mildly favourable (a real, documented effect).
        pam_proximal_bonus = 0.1 if spacer[-1] == "G" else 0.0
        score = 0.85 * gc_term + pam_proximal_bonus
        return max(0.0, min(1.0, score))


class MockOffTargetScorer:
    """Deterministic stand-in for Cas-OFFinder + CFD.

    Fabricates a small, spacer-derived set of putative off-target sites and a
    max CFD. Replace with a real genome scan; the report shape is unchanged.
    """

    name = "mock_seed"
    version = "0.1.0"

    def scan(self, spacer: str, genome_build: str) -> OffTargetReport:
        spacer = normalize(spacer)
        base = _unit_hash(spacer, salt="offtarget")
        # 0-3 putative sites, worst-case CFD scaled down from the seed value.
        site_count = int(base * 4)
        sites = []
        worst = 0.0
        for k in range(site_count):
            cfd = round(_unit_hash(spacer, salt=f"cfd{k}") * 0.4, 3)
            worst = max(worst, cfd)
            sites.append(
                OffTargetSite(
                    sequence=spacer,  # placeholder; real scan returns mismatch seq
                    mismatches=1 + (k % 3),
                    cfd=cfd,
                    locus=f"chr?:{int(_unit_hash(spacer, salt=f'loc{k}') * 1e7)}",
                )
            )
        return OffTargetReport(
            max_cfd=worst,
            site_count=site_count,
            sites=sites,
            scorer=f"{self.name}@{self.version}",
        )


class MockRepairOutcomePredictor:
    """Deterministic stand-in for inDelphi / FORECasT / Lindel.

    Produces a plausible indel genotype distribution whose frameshift fraction is
    seeded by the cut-site context. Replace with a real predictor; the
    ``RepairOutcome`` shape is unchanged.
    """

    name = "mock_indel"
    version = "0.1.0"

    def predict(self, sequence: str, cutsite: int) -> RepairOutcome:
        seed = _unit_hash(f"{sequence}:{cutsite}", salt="repair")
        frameshift = round(0.55 + 0.4 * seed, 3)  # 0.55-0.95
        one_bp_del = round(0.3 + 0.2 * seed, 3)
        one_bp_ins = round(0.15 + 0.1 * (1 - seed), 3)
        return RepairOutcome(
            frameshift_fraction=min(1.0, frameshift),
            top_outcomes=[
                {"1bp_deletion": one_bp_del},
                {"1bp_insertion": one_bp_ins},
                {"other_indels": round(max(0.0, 1 - one_bp_del - one_bp_ins), 3)},
            ],
            predictor=f"{self.name}@{self.version}",
        )
