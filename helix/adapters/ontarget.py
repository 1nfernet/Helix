"""On-target efficiency scorers.

``RuleSet1OnTargetScorer`` is a faithful, independent implementation of the
Doench 2014 "Rule Set 1" model — a real, published on-target activity model, not
a heuristic. Coefficients live in :mod:`helix.adapters.data.doench2014` (cited to
the paper); the formula here was cross-checked to match CRISPOR's reference
``calcDoenchScores`` on random 30-mers.

The next rung up (Rule Set 2 / Azimuth, a gradient-boosted ML model) is a future
drop-in behind the same ``OnTargetScorer`` Protocol.
"""

from __future__ import annotations

import math

from helix.adapters.base import ScorerContextError
from helix.adapters.data import doench2014 as d
from helix.bio import normalize

_MER_LEN = 30  # 4 bp 5' + 20 bp protospacer + 3 bp PAM + 3 bp 3'


class RuleSet1OnTargetScorer:
    """Doench 2014 Rule Set 1. Expects the 30-mer context on the guide's strand."""

    name = "rule_set_1"
    version = "doench2014"

    def score(self, spacer: str, context: str) -> float:
        mer = normalize(context)
        if len(mer) != _MER_LEN:
            raise ScorerContextError(
                f"rule_set_1 needs a {_MER_LEN}-mer context (4+20+3+3); got {len(mer)} nt"
            )

        score = d.INTERCEPT

        # GC term over the 20 nt protospacer (positions 4..24 of the 30-mer).
        guide = mer[4:24]
        gc = guide.count("G") + guide.count("C")
        gc_weight = d.GC_LOW if gc <= 10 else d.GC_HIGH
        score += abs(10 - gc) * gc_weight

        # Position-specific single- and di-nucleotide contributions.
        for pos, subseq, weight in d.PARAMS:
            if mer[pos : pos + len(subseq)] == subseq:
                score += weight

        return 1.0 / (1.0 + math.exp(-score))
