"""Tests for the autonomous refine loop (offline, scripted fake LLM)."""

import json

from helix.agents.critic import DesignCritic
from helix.agents.refine import RefineLoop
from helix.frontend.loader import parse_spec


class FakeLLM:
    def __init__(self, responses):
        self._r = list(responses)
        self.calls = 0

    def complete(self, system, user, *, max_tokens=1024):
        self.calls += 1
        return self._r.pop(0)


def _crit(edits):
    return json.dumps({"summary": "", "findings": [], "suggested_constraint_edits": edits})


def _spec():
    return parse_spec(
        {"name": "r", "target": {"gene": "X", "sequence": "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 4},
         "constraints": {"on_target_min_efficiency": 0.0, "guides_count": 1, "off_target_max_cfd": 0.2}}
    )


def _loop(responses, max_iters=5):
    return RefineLoop(DesignCritic(FakeLLM(responses)), max_iters=max_iters).run(_spec())


def test_converges_when_no_more_edits():
    result = _loop([_crit({"off_target_max_cfd": 0.15}), _crit({})])
    assert result.converged and "no further" in result.reason
    assert len(result.steps) == 1 and result.steps[0].adopted
    assert result.spec.constraints.off_target_max_cfd == 0.15  # edit applied


def test_converges_on_noop_edit():
    # Same edit twice: first changes the spec, second is a no-op -> converge.
    result = _loop([_crit({"off_target_max_cfd": 0.15}), _crit({"off_target_max_cfd": 0.15})])
    assert result.converged and "do not change" in result.reason
    assert len(result.steps) == 1


def test_hits_max_iters():
    result = _loop(
        [_crit({"off_target_max_cfd": v}) for v in (0.19, 0.18, 0.17)], max_iters=2
    )
    assert not result.converged and "max_iters" in result.reason
    assert len(result.steps) == 2


def test_infeasibility_guardrail_keeps_last_feasible():
    # Edit that makes the design infeasible must be rejected, prior design kept.
    result = _loop([_crit({"on_target_min_efficiency": 0.999})])
    assert result.converged and "infeasible" in result.reason
    assert result.design.feasible  # kept the previous, feasible design
    assert result.spec.constraints.on_target_min_efficiency == 0.0  # edit not adopted
    assert result.steps[-1].adopted is False
