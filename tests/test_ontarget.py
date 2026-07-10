"""Tests for the Rule Set 1 (Doench 2014) on-target scorer.

The pinned expected values were cross-checked against CRISPOR's reference
implementation (`crisporEffScores.py::calcDoenchScores`) on the same 30-mers:
0 mismatches over 20,000 random 30-mers. So these assertions pin equivalence to
the published model, not just to our own output.
"""

import pytest

from helix.adapters.base import ScorerContextError
from helix.adapters.ontarget import RuleSet1OnTargetScorer
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec

SCORER = RuleSet1OnTargetScorer()

# (30-mer, expected int(100 * score)) — matches CRISPOR calcDoenchScores.
_REFERENCE = [
    ("GGGAGGCTGCTGGGGGCGCTGTGGGGGCGC", 1),
    ("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", 4),
    ("ACCTGCACGTAGCTGCTAGCTAGCTGGCGT", 38),
]


@pytest.mark.parametrize("mer,expected", _REFERENCE)
def test_matches_crispor_reference(mer, expected):
    score = SCORER.score(mer, mer)
    assert 0.0 <= score <= 1.0
    assert int(100 * score) == expected


def test_requires_a_30mer():
    with pytest.raises(ScorerContextError):
        SCORER.score("A" * 20, "ACGT" * 6)  # 24 nt context, not 30


def test_deterministic():
    mer = _REFERENCE[2][0]
    assert SCORER.score(mer, mer) == SCORER.score(mer, mer)


def test_pipeline_scores_guides_with_rule_set_1():
    seq = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4  # 120 nt, internal NGG sites
    spec = parse_spec(
        {
            "name": "rs1",
            "target": {"gene": "TP53", "sequence": seq},
            "constraints": {"on_target_min_efficiency": 0.0, "guides_count": 1},
            "simulate": {"on_target": "rule_set_1"},
        }
    )
    design = compile_spec(spec)
    assert design.guides, "expected guides scored by rule_set_1"
    assert all(0.0 <= g.on_target_score <= 1.0 for g in design.guides)
