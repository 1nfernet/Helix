"""Design-critic agent: adversarially review a resolved design.

The critic reads a compiled design and returns structured findings plus, where
useful, *suggested spec edits*. It holds the same trust boundary as the other
agents: it never mutates the design and its machine-applicable suggestions are
limited to constraint knobs, each validated against the IR before being offered.
Free-text findings may say anything (for humans); only validated edits can be
re-applied and re-compiled.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, ValidationError

from helix.agents.llm import LLMClient, extract_json_object
from helix.ir.design import ResolvedDesign
from helix.ir.spec import Constraints, ExperimentSpec

_SEVERITIES = ("info", "warning", "critical")


class CritiqueFinding(BaseModel):
    severity: str = "info"
    category: str = "general"
    message: str
    suggestion: str = ""


class Critique(BaseModel):
    summary: str = ""
    findings: List[CritiqueFinding] = []
    suggested_constraint_edits: Dict[str, Any] = {}
    dropped_edits: List[str] = []


_SYSTEM = (
    "You are an adversarial reviewer of a gene-editing design (knockout, base/prime "
    "editing, HDR knock-in, deletion, or CRISPRi/a) produced by a deterministic "
    "compiler. Find real weaknesses: weak on-target efficiency, off-target risk, low "
    "editing/frameshift likelihood, infeasibility, thin guide margins, bystander or "
    "re-cutting risk, delivery/validation gaps. You do NOT edit the design; you "
    "only advise. Reply with a JSON object: "
    '{"summary": "...", "findings": [{"severity": "info|warning|critical", '
    '"category": "...", "message": "...", "suggestion": "..."}], '
    '"suggested_constraint_edits": {"<constraint_field>": <value>}}. '
    "Only propose constraint edits that would plausibly improve the design; use "
    "the exact IR field names."
)


def _digest(spec: ExperimentSpec, design: ResolvedDesign) -> str:
    """A compact, factual summary of the design for the reviewer."""
    lines = [
        f"name={design.spec_name}",
        f"modality={design.modality}",
        f"enzyme={design.resolved_enzyme.value}",
        f"feasible={design.feasible}",
        f"safety_allowed={design.safety.allowed}",
        f"candidates={len(design.guides)} selected={len(design.selected)} pegRNAs={len(design.prime_edits)}",
        f"constraints={spec.constraints.model_dump()}",
        f"delivery={spec.deliver.value} validate={spec.validate_with.value}",
    ]
    if design.delivery:
        lines.append(f"delivery_recommended={design.delivery.recommended} cargo_kb={design.delivery.cargo_kb}")
    if design.infeasibility_notes:
        lines.append("infeasibility=" + "; ".join(design.infeasibility_notes))
    for i, g in enumerate(design.selected, 1):
        parts = [
            f"guide{i}: spacer={g.spacer} strand={g.strand.value}",
            f"on_target={g.on_target_score} max_cfd={g.off_target.max_cfd}",
        ]
        if g.repair:
            parts.append(f"frameshift={g.repair.frameshift_fraction}")
        if g.base_edit:
            parts.append(f"window={g.base_edit.window}->{g.base_edit.edited_product} bystanders={g.base_edit.bystander_count}")
        if g.hdr:
            parts.append(f"cut_to_edit={g.hdr.cut_to_edit_distance} pam_disrupted={g.hdr.pam_disrupted}")
        if g.regulation:
            parts.append(f"tss_offset={g.regulation.tss_offset} optimal={g.regulation.optimal}")
        lines.append(" ".join(parts))
    for i, p in enumerate(design.prime_edits[:3], 1):
        lines.append(
            f"pegRNA{i}: spacer={p.spacer} edit={p.edit} pbs_len={len(p.pbs)} rtt_len={len(p.rtt)} "
            f"pred_eff={p.predicted_efficiency} on_target={p.on_target_score} "
            f"pe3={'yes' if p.pe3_nick_spacer else 'no'}"
        )
    return "\n".join(lines)


def _validate_edits(
    spec: ExperimentSpec, raw: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    """Keep only constraint edits that are real fields and validate cleanly."""
    fields = set(Constraints.model_fields.keys())
    base = spec.constraints.model_dump()
    valid: Dict[str, Any] = {}
    dropped: List[str] = []
    for key, value in (raw or {}).items():
        if key not in fields:
            dropped.append(f"{key} (unknown constraint)")
            continue
        try:
            Constraints(**{**base, key: value})
        except ValidationError:
            dropped.append(f"{key}={value!r} (invalid)")
            continue
        valid[key] = value
    return valid, dropped


class DesignCritic:
    """Review a design with an LLM; validate any suggested edits deterministically."""

    name = "critic"

    def __init__(self, client: LLMClient):
        self._client = client

    def review(self, spec: ExperimentSpec, design: ResolvedDesign) -> Critique:
        reply = self._client.complete(_SYSTEM, _digest(spec, design), max_tokens=1200)
        data = extract_json_object(reply)

        findings = []
        for f in data.get("findings", []):
            sev = f.get("severity", "info")
            findings.append(
                CritiqueFinding(
                    severity=sev if sev in _SEVERITIES else "info",
                    category=f.get("category", "general"),
                    message=f.get("message", ""),
                    suggestion=f.get("suggestion", ""),
                )
            )

        valid_edits, dropped = _validate_edits(spec, data.get("suggested_constraint_edits", {}))
        return Critique(
            summary=data.get("summary", ""),
            findings=findings,
            suggested_constraint_edits=valid_edits,
            dropped_edits=dropped,
        )


def apply_constraint_edits(spec: ExperimentSpec, edits: Dict[str, Any]) -> ExperimentSpec:
    """Return a new spec with the given (already-validated) constraint edits applied."""
    data = spec.model_dump()
    data["constraints"] = {**data["constraints"], **edits}
    return ExperimentSpec.model_validate(data)
