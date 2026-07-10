"""The compiler orchestrator: ``compile_spec``.

Wires the stages together in a single, readable function. Each stage is a small
module you can test in isolation; this file is just the assembly order.
"""

from __future__ import annotations

from typing import Optional

from helix.adapters.registry import AdapterRegistry, default_registry
from helix.agents.strategy import DeliveryAwareStrategyResolver, StrategyResolver
from helix.compiler import (
    base_editor,
    deletion_designer,
    guide_designer,
    hdr_designer,
    prime_editor,
    regulation_designer,
    target_resolver,
)
from helix.compiler.constraints import evaluate_and_select, evaluate_and_select_prime
from helix.compiler.variants import annotate_variants
from helix.compiler.delivery import recommend_delivery
from helix.compiler.primers import design_validation_primers
from helix.compiler.provenance import build_provenance
from helix.ir.design import ResolvedDesign
from helix.ir.enums import Enzyme, Modality
from helix.ir.spec import ExperimentSpec
from helix.safety.screen import BiosecurityScreen


def compile_spec(
    spec: ExperimentSpec,
    registry: Optional[AdapterRegistry] = None,
    strategy: Optional[StrategyResolver] = None,
) -> ResolvedDesign:
    """Compile an intent spec into a fully resolved, provenance-stamped design."""
    registry = registry or default_registry()
    strategy = strategy or DeliveryAwareStrategyResolver()

    # 1. Safety gate — before any work.
    safety = BiosecurityScreen().screen(spec)
    enzyme = strategy.resolve_enzyme(spec)

    adapters = {"strategy": f"{strategy.name}@{strategy.version}"}

    modality = spec.strategy.modality
    if modality in (Modality.CRISPRI, Modality.CRISPRA):
        enzyme = Enzyme.DCAS9  # CRISPRi/a always use catalytically-dead Cas9

    if not safety.allowed:
        return ResolvedDesign(
            spec_name=spec.name,
            modality=modality.value,
            resolved_enzyme=enzyme,
            target=None,
            guides=[],
            selected=[],
            feasible=False,
            infeasibility_notes=["Run blocked by biosecurity screen."],
            safety=safety,
            provenance=build_provenance(spec, adapters),
        )

    # 2. Resolve adapters named in the spec's `simulate` block.
    seq_provider = registry.sequence(spec.simulate.sequence_provider)
    on_target = registry.on_target(spec.simulate.on_target)
    # Rule Set 1 is SpCas9-only; a delivery-aware SaCas9/Cas12a choice needs an
    # enzyme-agnostic scorer, so fall back to the heuristic.
    if enzyme is not Enzyme.SPCAS9 and spec.simulate.on_target == "rule_set_1":
        on_target = registry.on_target("heuristic_gc")
    off_target = registry.off_target(spec.simulate.off_target)
    repair = registry.repair(spec.simulate.repair_outcome)
    adapters.update(
        sequence=f"{seq_provider.name}@{seq_provider.version}",
        on_target=f"{on_target.name}@{on_target.version}",
        off_target=f"{off_target.name}@{off_target.version}",
        repair=f"{repair.name}@{repair.version}",
    )

    # Learned outcome models, resolved for the relevant modality (stamped in provenance).
    be_model = pe_model = None
    if modality is Modality.BASE_EDIT:
        be_model = registry.base_edit_model(spec.simulate.base_edit_model)
        adapters["base_edit_model"] = be_model.name
    elif modality is Modality.PRIME_EDIT:
        pe_model = registry.prime_edit_model(spec.simulate.prime_edit_model)
        adapters["prime_edit_model"] = pe_model.name

    # 3. Resolve target, then design per modality.
    target = target_resolver.resolve_target(spec, seq_provider)

    # Population variants overlapping the window (opt-in; Null returns none offline).
    variant_provider = registry.variant(spec.simulate.variant_source)
    variants = variant_provider.variants(target)
    if spec.simulate.variant_source != "none":
        adapters["variant"] = f"{variant_provider.name}@{variant_provider.version}"

    common = dict(
        spec_name=spec.name,
        modality=modality.value,
        resolved_enzyme=enzyme,
        target=target,
        delivery=recommend_delivery(spec, enzyme),
        safety=safety,
        provenance=build_provenance(spec, adapters),
    )

    if modality is Modality.PRIME_EDIT:
        if not spec.target.edit:
            raise ValueError("prime editing requires target.edit (e.g. 'A>G @ 12').")
        pegs = prime_editor.design_prime_edits(
            target, enzyme, spec.target.edit, on_target, off_target, model=pe_model
        )
        selection = evaluate_and_select_prime(pegs, spec.constraints)
        return ResolvedDesign(
            prime_edits=selection.ranked, selected=[],
            feasible=selection.feasible, infeasibility_notes=selection.notes, **common,
        )

    if modality is Modality.DELETION:
        if not spec.target.delete:
            raise ValueError("deletion requires target.delete (e.g. '40..90').")
        res = deletion_designer.design_deletion(
            target, enzyme, spec.target.delete, on_target, off_target, spec.constraints
        )
        primers = design_validation_primers(target, res.selected)
        return ResolvedDesign(
            guides=res.ranked, selected=res.selected, deletion=res.plan,
            feasible=res.feasible, infeasibility_notes=res.notes,
            validation_primers=primers, **common,
        )

    if modality is Modality.BASE_EDIT:
        if spec.strategy.editor is None:
            raise ValueError("base editing requires strategy.editor (CBE or ABE).")
        # Optional target.edit ('C>T @ 40') focuses the design on guides whose
        # editing window covers that specific base (set when a base is picked in 3D).
        target_pos: Optional[int] = None
        if spec.target.edit:
            try:
                _, _, target_pos = prime_editor.parse_edit(spec.target.edit)
            except ValueError:
                target_pos = None
        guides = base_editor.design_base_edits(
            target, enzyme, spec.strategy.editor, on_target, off_target,
            model=be_model, target_pos=target_pos,
        )
    elif modality is Modality.HDR:
        if not spec.target.edit:
            raise ValueError("HDR knock-in requires target.edit (e.g. 'G>A @ 74' or '->FLAG @ 40').")
        if spec.strategy.donor is None:
            raise ValueError("HDR knock-in requires strategy.donor (ssodn or dsdna).")
        guides = hdr_designer.design_hdr(
            target, enzyme, spec.target.edit, spec.strategy.donor, on_target, off_target
        )
    elif modality in (Modality.CRISPRI, Modality.CRISPRA):
        guides = regulation_designer.design_regulation(
            target, modality, on_target, off_target, spec.target.tss
        )
    else:  # CRISPR_KO
        guides = guide_designer.design_guides(target, enzyme, on_target, off_target, repair)

    annotate_variants(guides, variants, enzyme)
    selection = evaluate_and_select(guides, spec.constraints)
    primers = design_validation_primers(target, selection.selected)
    return ResolvedDesign(
        guides=selection.ranked, selected=selection.selected,
        feasible=selection.feasible, infeasibility_notes=selection.notes,
        validation_primers=primers, **common,
    )
