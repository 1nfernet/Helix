"""A canned, offline LLM client for demoing/testing the agent UI without a key.

Enabled only when ``HELIX_FAKE_LLM`` is set. It returns a fixed (offline-compilable)
Helix spec for authoring requests and a fixed critique JSON for reviews — so the
end-to-end UI flow (draft → compile, critique → apply) works with no network.
"""

from __future__ import annotations

from typing import Optional

_DEMO_SPEC = """\
helix "AI_TP53_KO" {
  organism: human(GRCh38)
  cell_line: HEK293T

  target: gene(TP53) {
    goal: knockout
    sequence: "ACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGTACCTGCACGTAGCTGCTAGCTAGCTGGCGT"
  }

  strategy { modality: crispr_ko; enzyme: auto }

  constraints {
    on_target.min_efficiency: 0.0
    off_target.max_cfd: 0.3
    guides.count: 3
    avoid: [ homopolymer(>=5) ]
  }

  simulate { sequence_provider: inline; on_target: heuristic_gc; off_target: mock_seed; repair_outcome: mock_indel }
  deliver: rnp
  validate: amplicon_seq
}
"""

_DEMO_CRITIQUE = (
    '{"summary": "Feasible, but the off-target margin is thin and delivery could be tightened.", '
    '"findings": ['
    '{"severity": "warning", "category": "off-target", "message": "Top guide max CFD is close to the 0.3 threshold.", "suggestion": "Tighten off_target.max_cfd to 0.2."}, '
    '{"severity": "info", "category": "efficiency", "message": "On-target efficiencies are moderate.", "suggestion": "Consider a higher min_efficiency once you have candidates to spare."}'
    '], "suggested_constraint_edits": {"off_target_max_cfd": 0.2}}'
)


class DemoLLMClient:
    """Offline stand-in for the Anthropic client (canned replies, fake usage)."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or "demo-offline"
        self.last_usage = {
            "input_tokens": 1200, "output_tokens": 260,
            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
        }

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        return _DEMO_CRITIQUE if "reviewer" in system.lower() else _DEMO_SPEC
