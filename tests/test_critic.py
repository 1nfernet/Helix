"""Tests for the design-critic agent (offline, fake LLM)."""

import json

from helix.agents.critic import DesignCritic, apply_constraint_edits
from helix.compiler.pipeline import compile_spec
from helix.frontend.loader import parse_spec


class FakeLLM:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def complete(self, system, user, *, max_tokens=1024):
        self.calls.append((system, user))
        return self._response


def _design_and_spec():
    spec = parse_spec(
        {"name": "c", "target": {"gene": "TP53",
                                 "sequence": "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4}}
    )
    return spec, compile_spec(spec)


_REPLY = json.dumps(
    {
        "summary": "Reasonable, but off-target margins are thin.",
        "findings": [
            {"severity": "warning", "category": "off_target",
             "message": "max CFD near threshold", "suggestion": "tighten off_target.max_cfd"},
            {"severity": "note-bad", "category": "delivery", "message": "RNP ok"},
        ],
        "suggested_constraint_edits": {
            "off_target_max_cfd": 0.1,   # valid
            "guides_count": 5,           # valid
            "bogus_key": 3,              # unknown -> dropped
            "on_target_min_efficiency": 2.0,  # out of range -> dropped
        },
    }
)


def test_critic_parses_findings_and_validates_edits():
    spec, design = _design_and_spec()
    critique = DesignCritic(FakeLLM(_REPLY)).review(spec, design)

    assert len(critique.findings) == 2
    assert critique.findings[1].severity == "info"  # unknown severity normalized
    assert critique.suggested_constraint_edits == {"off_target_max_cfd": 0.1, "guides_count": 5}
    assert len(critique.dropped_edits) == 2  # bogus_key + out-of-range


def test_digest_includes_design_facts():
    spec, design = _design_and_spec()
    critic = DesignCritic(FakeLLM(_REPLY))
    critic.review(spec, design)
    _, user = critic._client.calls[0]
    assert "enzyme=SpCas9" in user and "feasible=" in user


def test_apply_constraint_edits_roundtrips():
    spec, _ = _design_and_spec()
    revised = apply_constraint_edits(spec, {"off_target_max_cfd": 0.1, "guides_count": 5})
    assert revised.constraints.off_target_max_cfd == 0.1
    assert revised.constraints.guides_count == 5
    # original untouched
    assert spec.constraints.guides_count == 3


def test_refine_loop_recompiles_with_suggested_edits():
    spec, design = _design_and_spec()
    critique = DesignCritic(FakeLLM(_REPLY)).review(spec, design)
    revised = apply_constraint_edits(spec, critique.suggested_constraint_edits)
    redesign = compile_spec(revised)
    assert redesign.spec_name == design.spec_name  # loop closed: spec -> critique -> spec -> design
